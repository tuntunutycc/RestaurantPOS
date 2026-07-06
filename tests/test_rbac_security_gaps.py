"""RBAC security gap coverage: admin isolation, root powers, password change, account read-only."""

import uuid

import pytest

from auth import verify_password
from models import Category, User
from rbac import (
    ROLE_ACCOUNT,
    ROLE_ADMIN,
    ROLE_CASHIER,
    ROLE_ROOT,
    ROLE_WAITER,
    uses_multi_device_sessions,
    uses_single_device_sessions,
)


# --- Session policy unit checks (backend contract) ---


@pytest.mark.parametrize(
    "role,expect_single,expect_multi",
    [
        (ROLE_ROOT, False, True),
        (ROLE_ADMIN, False, True),
        (ROLE_CASHIER, True, False),
        (ROLE_WAITER, True, False),
        (ROLE_ACCOUNT, True, False),
    ],
)
def test_session_policy_role_helpers(role, expect_single, expect_multi):
    assert uses_single_device_sessions(role) is expect_single
    assert uses_multi_device_sessions(role) is expect_multi


# --- Admin isolation & root endpoint security ---


def _create_second_admin(client, auth_headers, username: str | None = None) -> dict:
    username = username or f"adminb_{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/api/root/admins",
        headers=auth_headers("root"),
        json={"username": username, "password": "adminb12345"},
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.parametrize(
    "method,path_template,payload",
    [
        ("get", "/api/root/admins", None),
        ("post", "/api/root/admins", {"username": "blocked_admin", "password": "blocked1"}),
    ],
)
def test_admin_forbidden_on_root_admins_list_and_create(
    client, auth_headers, method, path_template, payload
):
    if method == "get":
        res = client.get(path_template, headers=auth_headers("admin"))
    else:
        payload = dict(payload)
        payload["username"] = f"{payload['username']}_{uuid.uuid4().hex[:6]}"
        res = client.post(path_template, headers=auth_headers("admin"), json=payload)
    assert res.status_code == 403, res.text


def test_admin_cannot_edit_other_admin(client, auth_headers):
    admin_b = _create_second_admin(client, auth_headers)
    res = client.put(
        f"/api/admin/users/{admin_b['id']}",
        headers=auth_headers("admin"),
        json={
            "username": admin_b["username"],
            "role": "admin",
            "password": "hacked123",
        },
    )
    assert res.status_code == 403, res.text
    assert "cannot edit admin" in res.json()["detail"].lower()


def test_admin_cannot_delete_other_admin(client, auth_headers):
    admin_b = _create_second_admin(client, auth_headers)
    res = client.delete(
        f"/api/admin/users/{admin_b['id']}",
        headers=auth_headers("admin"),
    )
    assert res.status_code == 403, res.text
    assert "cannot delete admin" in res.json()["detail"].lower()


def test_admin_forbidden_on_root_admin_update_delete_reset(client, auth_headers):
    admin_b = _create_second_admin(client, auth_headers)
    admin_id = admin_b["id"]

    update = client.put(
        f"/api/root/admins/{admin_id}",
        headers=auth_headers("admin"),
        json={"username": admin_b["username"], "password": ""},
    )
    assert update.status_code == 403, update.text

    reset = client.post(
        f"/api/root/admins/{admin_id}/reset-password",
        headers=auth_headers("admin"),
        json={"new_password": "reset12345"},
    )
    assert reset.status_code == 403, reset.text

    delete = client.delete(
        f"/api/root/admins/{admin_id}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 403, delete.text


# --- Root admin governance (update / delete / reset password) ---


def test_root_updates_deletes_and_resets_admin_password(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:6]
    username = f"gov_{suffix}"
    updated_username = f"gov_{suffix}_v2"
    initial_password = "initpass1"
    reset_password = "resetpass9"

    create = client.post(
        "/api/root/admins",
        headers=auth_headers("root"),
        json={"username": username, "password": initial_password},
    )
    assert create.status_code == 200, create.text
    admin_id = create.json()["id"]

    update = client.put(
        f"/api/root/admins/{admin_id}",
        headers=auth_headers("root"),
        json={"username": updated_username, "password": "updatedpass1"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["username"] == updated_username

    listed = client.get("/api/root/admins", headers=auth_headers("root"))
    assert listed.status_code == 200
    assert any(u["id"] == admin_id and u["username"] == updated_username for u in listed.json())

    reset = client.post(
        f"/api/root/admins/{admin_id}/reset-password",
        headers=auth_headers("root"),
        json={"new_password": reset_password},
    )
    assert reset.status_code == 200, reset.text

    login_ok = client.post(
        "/api/auth/login",
        json={"username": updated_username, "password": reset_password, "device_id": "pytest-root-reset"},
    )
    assert login_ok.status_code == 200, login_ok.text

    delete = client.delete(
        f"/api/root/admins/{admin_id}",
        headers=auth_headers("root"),
    )
    assert delete.status_code == 200, delete.text

    listed_after = client.get("/api/root/admins", headers=auth_headers("root"))
    assert listed_after.status_code == 200
    assert not any(u["id"] == admin_id for u in listed_after.json())

    db_session.expire_all()
    row = db_session.query(User).filter(User.id == admin_id).first()
    assert row is not None
    assert row.is_deleted is True


def test_root_create_admin_writes_audit_log(client, auth_headers):
    username = f"audadmin_{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/api/root/admins",
        headers=auth_headers("root"),
        json={"username": username, "password": "auditpass1"},
    )
    assert res.status_code == 200, res.text
    admin_id = res.json()["id"]

    logs = client.get(
        "/api/root/audit-logs?action=root_create_admin",
        headers=auth_headers("root"),
    )
    assert logs.status_code == 200
    match = next((row for row in logs.json() if row.get("target_user_id") == admin_id), None)
    assert match is not None
    assert match.get("action") == "root_create_admin"


# --- Self-service password change ---


def _login_password(client, username: str, password: str) -> str:
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password, "device_id": "pytest-change-pw"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _assert_change_password_flow(client, *, username: str, old_password: str, new_password: str):
    token = _login_password(client, username, old_password)
    change = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password},
    )
    assert change.status_code == 200, change.text
    assert change.json().get("changed") is True

    old_login = client.post(
        "/api/auth/login",
        json={"username": username, "password": old_password, "device_id": "pytest-old-pw"},
    )
    assert old_login.status_code == 401, old_login.text

    new_login = client.post(
        "/api/auth/login",
        json={"username": username, "password": new_password, "device_id": "pytest-new-pw"},
    )
    assert new_login.status_code == 200, new_login.text


@pytest.mark.parametrize(
    "role,username,old_password,new_password",
    [
        ("root", "root", "root123", "rootNew123"),
        ("admin", "admin", "admin123", "adminNew123"),
    ],
)
def test_change_password_succeeds_for_password_roles(
    client, seed_users, role, username, old_password, new_password
):
    _assert_change_password_flow(
        client,
        username=username,
        old_password=old_password,
        new_password=new_password,
    )


def test_change_password_rejects_wrong_current_password(client, auth_headers):
    token = auth_headers("admin")["Authorization"].split(" ", 1)[1]
    res = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrong-password", "new_password": "newpass123"},
    )
    assert res.status_code == 400, res.text
    assert "incorrect" in res.json()["detail"].lower()


@pytest.mark.parametrize("role", ["cashier", "waiter", "account"])
def test_change_password_forbidden_for_pin_roles(client, auth_headers, role):
    res = client.post(
        "/api/auth/change-password",
        headers=auth_headers(role),
        json={"current_password": "x", "new_password": "newpass123"},
    )
    assert res.status_code == 403, res.text


def test_change_password_updates_hash(client, db_session, seed_users):
    user = seed_users["admin"]
    new_password = "hashCheck9"
    token = _login_password(client, "admin", "admin123")
    res = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "admin123", "new_password": new_password},
    )
    assert res.status_code == 200, res.text
    db_session.refresh(user)
    assert verify_password(new_password, user.password_hash)
    assert not verify_password("admin123", user.password_hash)


# --- Account role: read-only mutations blocked ---


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("post", "/api/admin/users", {"username": "blocked_waiter", "role": "waiter", "pin_code": "1212"}),
        ("post", "/api/categories/", {"name": f"Acc-Cat-{uuid.uuid4().hex[:6]}"}),
    ],
)
def test_account_forbidden_on_staff_and_category_create(client, auth_headers, seed_users, method, path, payload):
    if "username" in payload:
        payload = dict(payload)
        payload["username"] = f"acc_blk_{uuid.uuid4().hex[:6]}"
    if "name" in payload:
        payload = dict(payload)
        payload["name"] = f"Acc-Cat-{uuid.uuid4().hex[:6]}"

    headers = auth_headers("account")
    if method == "post":
        res = client.post(path, headers=headers, json=payload)
    else:
        raise AssertionError(f"unsupported method {method}")
    assert res.status_code == 403, res.text


def test_account_forbidden_on_staff_update_and_delete(client, auth_headers, seed_users):
    waiter_id = seed_users["waiter"].id
    headers = auth_headers("account")

    update = client.put(
        f"/api/admin/users/{waiter_id}",
        headers=headers,
        json={"username": "waiter1", "role": "waiter", "pin_code": "1111"},
    )
    assert update.status_code == 403, update.text

    delete = client.delete(f"/api/admin/users/{waiter_id}", headers=headers)
    assert delete.status_code == 403, delete.text


def test_account_forbidden_on_menu_item_and_table_mutations(client, auth_headers, db_session):
    suffix = uuid.uuid4().hex[:6]
    cat = Category(name=f"Acc-Menu-Cat-{suffix}")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)

    headers = auth_headers("account")

    menu_create = client.post(
        "/api/menu-items/",
        headers=headers,
        json={
            "name": f"Acc-Item-{suffix}",
            "price": 5.0,
            "category_id": cat.id,
            "is_available": True,
            "modifiers_config": [],
        },
    )
    assert menu_create.status_code == 403, menu_create.text

    zone_create = client.post(
        "/api/zones",
        headers=headers,
        json={"name": f"Acc-Zone-{suffix}"},
    )
    assert zone_create.status_code == 403, zone_create.text

    table_create = client.post(
        "/api/tables",
        headers=headers,
        json={"name": f"Acc-Table-{suffix}", "zone_id": 1, "status": "available"},
    )
    assert table_create.status_code == 403, table_create.text
