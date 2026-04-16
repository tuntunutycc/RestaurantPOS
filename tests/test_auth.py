def test_login_pin_success(client, seed_users):
    res = client.post("/api/auth/login-pin", json={"pin_code": "1111"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body.get("access_token"), str) and body["access_token"]
    assert body["user"]["role"] == "waiter"


def test_login_pin_wrong_pin(client, seed_users):
    res = client.post("/api/auth/login-pin", json={"pin_code": "9999"})
    assert res.status_code == 401


def test_login_admin_success(client, seed_users):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["role"] == "admin"


def test_me_requires_auth(client, seed_users):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers("admin"))
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"

