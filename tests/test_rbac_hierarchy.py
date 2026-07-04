"""Automated RBAC creation hierarchy: ROOT -> ADMIN -> CASHIER/WAITER."""

import uuid

import pytest

STAFF_CREATE_URL = "/api/admin/users"
ROOT_ADMIN_CREATE_URL = "/api/root/admins"


def _unique(name: str) -> str:
    return f"{name}_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def hierarchy_users(client, auth_headers, seed_users):
    """Seed users plus fresh auth headers for hierarchy scenarios."""
    return {"seed": seed_users, "auth": auth_headers}


class TestScenario1RootCreatesAdmin:
    """Root can create admin accounts via the root governance API."""

    def test_root_creates_admin_returns_2xx(self, client, hierarchy_users):
        username = _unique("newadmin")
        res = client.post(
            ROOT_ADMIN_CREATE_URL,
            headers=hierarchy_users["auth"]("root"),
            json={"username": username, "password": "secure123", "pin_code": "5678"},
        )
        assert 200 <= res.status_code < 300, res.text
        body = res.json()
        assert body["username"] == username
        assert body["role"] == "admin"


class TestScenario2AdminCannotCreateAdmin:
    """Admin must not escalate privilege by creating another admin or root."""

    @pytest.mark.parametrize("privileged_role", ["admin", "root"])
    def test_admin_cannot_create_privileged_user_via_staff_api(
        self, client, hierarchy_users, privileged_role
    ):
        payload = {"username": _unique(f"blocked{privileged_role}"), "role": privileged_role}
        if privileged_role == "admin":
            payload["pin_code"] = "9999"
        else:
            payload["password"] = "rootpass1"

        res = client.post(
            STAFF_CREATE_URL,
            headers=hierarchy_users["auth"]("admin"),
            json=payload,
        )
        assert res.status_code == 403, res.text
        assert "cannot create admin or root" in res.json()["detail"].lower()


class TestScenario3AdminCreatesFloorStaff:
    """Admin can create cashier and waiter staff."""

    @pytest.mark.parametrize("role,pin", [("cashier", "3333"), ("waiter", "4444")])
    def test_admin_creates_floor_staff_returns_2xx(self, client, hierarchy_users, role, pin):
        username = _unique(role)
        res = client.post(
            STAFF_CREATE_URL,
            headers=hierarchy_users["auth"]("admin"),
            json={"username": username, "role": role, "pin_code": pin},
        )
        assert 200 <= res.status_code < 300, res.text
        body = res.json()
        assert body["username"] == username
        assert body["role"] == role


class TestScenario4FloorStaffCannotCreateUsers:
    """Cashier and waiter have no user-management privileges."""

    @pytest.mark.parametrize("role", ["cashier", "waiter"])
    def test_floor_staff_cannot_create_users(self, client, hierarchy_users, role):
        res = client.post(
            STAFF_CREATE_URL,
            headers=hierarchy_users["auth"](role),
            json={"username": _unique("blocked"), "role": "cashier", "pin_code": "5555"},
        )
        assert res.status_code == 403, res.text


class TestScenario5RootCannotBeCreatedViaStaffApi:
    """Root accounts must not be creatable through the standard staff user API."""

    @pytest.mark.parametrize("actor", ["admin", "root"])
    def test_root_role_blocked_on_staff_create_api(self, client, hierarchy_users, actor):
        res = client.post(
            STAFF_CREATE_URL,
            headers=hierarchy_users["auth"](actor),
            json={"username": _unique("fakeroot"), "role": "root", "password": "rootpass1"},
        )
        assert res.status_code == 403, res.text
