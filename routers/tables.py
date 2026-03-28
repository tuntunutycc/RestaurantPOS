"""Zone and Table management APIs."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import get_current_user, require_roles
from database import get_db
from models import Order, Table, User, Zone
from schemas import (
    TableCreate,
    TableGridItemResponse,
    TableResponse,
    TableUpdate,
    ZoneTableGridResponse,
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
    ZoneWithTablesResponse,
)

router = APIRouter(prefix="/api", tags=["zones-tables"])
OPEN_ORDER_STATUSES = ("open", "dining")


async def _broadcast_table_grid_updated(request: Request) -> None:
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast("table_grid_updated", {"refresh": True})


def _status_value(value) -> str:
    return getattr(value, "value", value)


# ---------- Zone CRUD (Admin) ----------
@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    return db.query(Zone).order_by(Zone.id.asc()).all()


@router.post("/zones", response_model=ZoneResponse)
def create_zone(
    body: ZoneCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Zone name is required")
    if db.query(Zone).filter(Zone.name == name).first():
        raise HTTPException(status_code=400, detail="Zone already exists")
    zone = Zone(name=name)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(
    zone_id: int,
    body: ZoneUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Zone name is required")
    if db.query(Zone).filter(Zone.name == name, Zone.id != zone_id).first():
        raise HTTPException(status_code=400, detail="Zone already exists")
    zone.name = name
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}")
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    table_ids = [t.id for t in (zone.tables or [])]
    if table_ids:
        # Prevent deleting a zone that still has active/unpaid orders on its tables.
        active_statuses = ("open", "dining", "pending", "completed")
        active_orders_count = (
            db.query(Order)
            .filter(
                Order.table_id.in_(table_ids),
                Order.status.in_(active_statuses),
            )
            .count()
        )
        if active_orders_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete zone with active/unpaid table orders",
            )

        # Keep historical paid orders by detaching them from soon-to-be-deleted tables.
        historical_orders = db.query(Order).filter(Order.table_id.in_(table_ids)).all()
        for order in historical_orders:
            order.table_id = None

    # Zone -> tables deletion is cascaded by ORM relationship.
    db.delete(zone)
    db.commit()
    return {"deleted": True, "zone_id": zone_id}


# ---------- Table CRUD (Admin) ----------
@router.get("/tables", response_model=list[TableResponse])
def list_tables(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    return db.query(Table).order_by(Table.id.asc()).all()


@router.post("/tables", response_model=TableResponse)
async def create_table(
    request: Request,
    body: TableCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    if not db.query(Zone).filter(Zone.id == body.zone_id).first():
        raise HTTPException(status_code=404, detail="Zone not found")
    name = body.name_or_number.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Table name_or_number is required")
    if db.query(Table).filter(Table.name_or_number == name).first():
        raise HTTPException(status_code=400, detail="Table name_or_number already exists")
    table = Table(name_or_number=name, zone_id=body.zone_id, status=body.status)
    db.add(table)
    db.commit()
    db.refresh(table)
    manager = getattr(request.app.state, "ws_manager", None)
    if manager:
        await manager.broadcast(
            "table_status_changed",
            {
                "table_id": table.id,
                "name_or_number": table.name_or_number,
                "zone_id": table.zone_id,
                "status": _status_value(table.status),
            },
        )
    await _broadcast_table_grid_updated(request)
    return table


@router.put("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    request: Request,
    table_id: int,
    body: TableUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    previous_status = table.status
    if body.zone_id is not None:
        if not db.query(Zone).filter(Zone.id == body.zone_id).first():
            raise HTTPException(status_code=404, detail="Zone not found")
        table.zone_id = body.zone_id
    if body.name_or_number is not None:
        name = body.name_or_number.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Table name_or_number is required")
        if db.query(Table).filter(Table.name_or_number == name, Table.id != table_id).first():
            raise HTTPException(status_code=400, detail="Table name_or_number already exists")
        table.name_or_number = name
    if body.status is not None:
        table.status = body.status
    db.commit()
    db.refresh(table)

    if body.status is not None and body.status != previous_status:
        manager = getattr(request.app.state, "ws_manager", None)
        if manager:
            await manager.broadcast(
                "table_status_changed",
                {
                    "table_id": table.id,
                    "name_or_number": table.name_or_number,
                    "zone_id": table.zone_id,
                    "status": _status_value(table.status),
                },
            )
        await _broadcast_table_grid_updated(request)
    return table


@router.delete("/tables/{table_id}")
def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(["admin"])),
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # Block deletion only if there are active/unpaid orders tied to this table.
    active_statuses = ("open", "dining", "pending", "completed")
    active_orders_count = (
        db.query(Order)
        .filter(
            Order.table_id == table_id,
            Order.status.in_(active_statuses),
        )
        .count()
    )
    if active_orders_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete table with active/unpaid orders",
        )

    # Keep historical paid orders, but detach them from the physical table record.
    historical_orders = db.query(Order).filter(Order.table_id == table_id).all()
    for order in historical_orders:
        order.table_id = None

    db.delete(table)
    db.commit()
    return {"deleted": True, "table_id": table_id}


# ---------- Waiter endpoint ----------
@router.get("/tables/status", response_model=list[ZoneWithTablesResponse])
def list_tables_with_status_by_zone(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    zones = db.query(Zone).order_by(Zone.id.asc()).all()
    return [ZoneWithTablesResponse.model_validate(z) for z in zones]


@router.get("/tables/grid", response_model=list[ZoneTableGridResponse])
def get_tables_grid(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    zones = db.query(Zone).order_by(Zone.id.asc()).all()

    active_orders = (
        db.query(Order)
        .filter(Order.status.in_(OPEN_ORDER_STATUSES))
        .order_by(Order.id.desc())
        .all()
    )
    active_order_id_by_table: dict[int, int] = {}
    for o in active_orders:
        if o.table_id is not None and o.table_id not in active_order_id_by_table:
            active_order_id_by_table[o.table_id] = o.id

    result = []
    for zone in zones:
        tables = []
        for table in getattr(zone, "tables", []) or []:
            status_value = getattr(getattr(table, "status", None), "value", getattr(table, "status", "available"))
            is_occupied = status_value == "occupied"
            tables.append(
                TableGridItemResponse(
                    id=table.id,
                    name=table.name,
                    zone_id=table.zone_id,
                    status=status_value,
                    active_order_id=active_order_id_by_table.get(table.id) if is_occupied else None,
                )
            )
        result.append(ZoneTableGridResponse(id=zone.id, name=zone.name, tables=tables))
    return result

