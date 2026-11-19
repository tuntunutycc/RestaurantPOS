"""Linked add-ons: an add-on option may follow a main menu item's price.

Spec: specs/feature-linked-addons

An add-on is one option inside ``MenuItem.modifiers_config`` (JSON). Two optional keys
make it a *linked* option:

* ``linked_menu_item_id`` - the main menu item (the *target*) whose ``price`` the add-on follows;
* ``price_override``      - a price used instead of the target's (``0`` is a real value).

Effective price of a linked option: ``price_override`` if set, else the target's current
``price`` (target alive), else the stored ``option["price"]`` (fallback). The stored
``price`` of a linked option is kept equal to the effective price by the server (on save and
when the target's price changes), so the fallback is never stale or accidentally ``0``.

No router imports here, so routers and tests can both use it.
"""

from __future__ import annotations

import copy
import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import MenuItem
from schemas import MAX_MENU_MONEY

LINK_KEY = "linked_menu_item_id"
OVERRIDE_KEY = "price_override"
MAX_HOLDERS_LISTED = 20


def _norm_group(value) -> str:
    return str(value or "").strip()


def _norm_name(value) -> str:
    return str(value or "").strip()


def dump_modifiers_config(groups) -> list[dict]:
    """Serialize validated ``ModifierGroup`` objects for the JSON column.

    The two link keys are dropped when empty, so an unlinked option is stored exactly as
    before this feature ``{name, price}``.
    """
    out: list[dict] = []
    for group in groups or []:
        data = group.model_dump(mode="json") if hasattr(group, "model_dump") else copy.deepcopy(group)
        for option in data.get("options") or []:
            for key in (LINK_KEY, OVERRIDE_KEY):
                if option.get(key) is None:
                    option.pop(key, None)
        out.append(data)
    return out


def _iter_options(config):
    """Yield (group_dict, option_dict) for a stored config, tolerating legacy / odd shapes."""
    if not isinstance(config, list):
        return
    for group in config:
        if not isinstance(group, dict):
            continue
        options = group.get("options")
        if not isinstance(options, list):
            continue
        for option in options:
            if isinstance(option, dict):
                yield group, option


def _live_target(db: Session, target_id) -> MenuItem | None:
    return (
        db.query(MenuItem)
        .filter(MenuItem.id == target_id, MenuItem.is_deleted.is_(False))
        .first()
    )


def effective_option_price(db: Session, option: dict) -> float:
    """The one pricing rule for an option (see module docstring)."""
    target_id = option.get(LINK_KEY)
    if target_id is None:
        return float(option.get("price") or 0.0)
    override = option.get(OVERRIDE_KEY)
    if override is not None:
        return float(override)
    target = _live_target(db, target_id)
    if target is not None:
        return float(target.price)
    return float(option.get("price") or 0.0)


def normalize_modifiers_for_save(db: Session, groups, holder_id: int | None) -> list[dict]:
    """Validate and complete ``modifiers_config`` before it is stored (FR-L1).

    Raises ``HTTPException`` (404 / 422) and never changes anything in the database.
    ``groups`` are validated ``ModifierGroup`` objects (or equivalent dicts).
    """
    config = dump_modifiers_config(groups)
    any_linked = False
    for _group, option in _iter_options(config):
        target_id = option.get(LINK_KEY)
        override = option.get(OVERRIDE_KEY)
        if target_id is None:
            if override is not None:
                raise HTTPException(
                    status_code=422,
                    detail=f"price_override of add-on '{_norm_name(option.get('name'))}' needs linked_menu_item_id",
                )
            continue
        any_linked = True
        if holder_id is not None and target_id == holder_id:
            raise HTTPException(status_code=422, detail="An add-on cannot link to its own menu item")
        target = _live_target(db, target_id)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Menu item id {target_id} not found")
        if not _norm_name(option.get("name")):
            option["name"] = target.name
        # The server owns the stored price of a linked option (fallback, never trusted from the client).
        option["price"] = float(override) if override is not None else float(target.price)

    if any_linked:
        seen: set[tuple[str, str]] = set()
        for group, option in _iter_options(config):
            key = (_norm_group(group.get("group")), _norm_name(option.get("name")))
            if key in seen:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Add-on '{key[1]}' appears more than once"
                        + (f" in group '{key[0]}'" if key[0] else "")
                        + "; names must be unique when an add-on is linked"
                    ),
                )
            seen.add(key)
    return config


def holders_linking_to(db: Session, target_id: int) -> list[MenuItem]:
    """Non-deleted menu items (other than the target itself) with an option linked to it."""
    rows = (
        db.query(MenuItem)
        .filter(MenuItem.is_deleted.is_(False), MenuItem.id != target_id)
        .order_by(MenuItem.id)
        .all()
    )
    return [
        row for row in rows
        if any(option.get(LINK_KEY) == target_id for _g, option in _iter_options(row.modifiers_config))
    ]


def linked_holders_message(target: MenuItem, holders: list[MenuItem]) -> str:
    listed = ", ".join(f"{h.name} (id {h.id})" for h in holders[:MAX_HOLDERS_LISTED])
    extra = len(holders) - MAX_HOLDERS_LISTED
    if extra > 0:
        listed += f", and {extra} more"
    return (
        f"Cannot delete '{target.name}' because it is linked as an add-on by: {listed}. "
        "Remove the link first."
    )


def sync_dependents_price(db: Session, target: MenuItem) -> list[MenuItem]:
    """Set the stored price of every following option to the target's price (FR-L3).

    Options with a ``price_override`` and unlinked options are not touched. Does not
    commit: the caller does it in the same transaction as the target's own change.
    Returns the holders that changed.
    """
    new_price = float(target.price)
    changed: list[MenuItem] = []
    for holder in holders_linking_to(db, target.id):
        config = copy.deepcopy(holder.modifiers_config)
        touched = False
        for _group, option in _iter_options(config):
            if option.get(LINK_KEY) != target.id or option.get(OVERRIDE_KEY) is not None:
                continue
            if float(option.get("price") or 0.0) != new_price:
                option["price"] = new_price
                touched = True
        if touched:
            holder.modifiers_config = config  # new object: SQLAlchemy sees the JSON change
            changed.append(holder)
    return changed


def resolve_linked_modifier(db: Session, menu_item: MenuItem, group, name) -> tuple[float, int] | None:
    """For an add-on picked on an order line: ``(effective price, target id)`` if the menu
    item has a **linked** option with this ``(group, name)``; ``None`` otherwise (then the
    caller keeps today's behaviour for unlinked add-ons)."""
    want = (_norm_group(group), _norm_name(name))
    for opt_group, option in _iter_options(menu_item.modifiers_config):
        if option.get(LINK_KEY) is None:
            continue
        if (_norm_group(opt_group.get("group")), _norm_name(option.get("name"))) != want:
            continue
        price = effective_option_price(db, option)
        if not math.isfinite(price) or abs(price) > MAX_MENU_MONEY:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The price of add-on '{want[1]}' on '{menu_item.name}' is not valid, "
                    "so it cannot be ordered. Ask the manager to fix the menu."
                ),
            )
        return price, int(option[LINK_KEY])
    return None
