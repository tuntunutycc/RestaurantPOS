import os
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from auth import hash_password
from database import Base, get_db
from models import User
from routers import auth as auth_router
from routers import kitchen_printers as kitchen_printers_router
from routers import menu as menu_router
from routers import orders as orders_router
from routers import reports as reports_router
from routers import root_users as root_users_router
from routers import setup as setup_router
from routers import tables as tables_router
from routers import users as users_router
from websocket_manager import ConnectionManager

TEST_DEVICE_ID = "pytest-device"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_get_db(db: Session):
    def _get_db_override():
        try:
            yield db
        finally:
            pass

    return _get_db_override


@pytest.fixture()
def app(db_session: Session) -> FastAPI:
    app = FastAPI()
    app.state.ws_manager = ConnectionManager()

    app.include_router(setup_router.router)
    app.include_router(root_users_router.router)
    app.include_router(auth_router.router)
    app.include_router(menu_router.router)
    app.include_router(orders_router.router)
    app.include_router(reports_router.router)
    app.include_router(tables_router.router)
    app.include_router(users_router.router)
    app.include_router(kitchen_printers_router.router)

    app.dependency_overrides[get_db] = _override_get_db(db_session)
    return app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def seed_users(db_session: Session) -> dict[str, User]:
    db_session.query(User).delete()
    db_session.commit()

    root = User(
        username="root",
        role="root",
        password_hash=hash_password("root123"),
        pin_code=None,
    )
    admin = User(
        username="admin",
        role="admin",
        password_hash=hash_password("admin123"),
        pin_code=None,
    )
    account = User(
        username="account1",
        role="account",
        password_hash=hash_password("acct123"),
        pin_code=None,
    )
    waiter = User(
        username="waiter1",
        role="waiter",
        password_hash=hash_password("changeme"),
        pin_code="1111",
    )
    cashier = User(
        username="cashier1",
        role="cashier",
        password_hash=hash_password("changeme"),
        pin_code="2222",
    )
    db_session.add_all([root, admin, account, waiter, cashier])
    db_session.commit()
    for u in (root, admin, account, waiter, cashier):
        db_session.refresh(u)
    return {
        "root": root,
        "admin": admin,
        "account": account,
        "waiter": waiter,
        "cashier": cashier,
    }


@pytest.fixture()
def auth_headers(client: TestClient, seed_users: dict[str, User]):
    def _get(role: str) -> dict[str, str]:
        role = str(role or "").strip().lower()
        if role in ("root", "admin", "account"):
            passwords = {"root": "root123", "admin": "admin123", "account": "acct123"}
            usernames = {"root": "root", "admin": "admin", "account": "account1"}
            res = client.post(
                "/api/auth/login",
                json={
                    "username": usernames[role],
                    "password": passwords[role],
                    "device_id": TEST_DEVICE_ID,
                },
            )
            assert res.status_code == 200, res.text
            token = res.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
        if role == "waiter":
            res = client.post(
                "/api/auth/login-pin",
                json={"pin_code": "1111", "device_id": TEST_DEVICE_ID},
            )
            assert res.status_code == 200, res.text
            return {"Authorization": f"Bearer {res.json()['access_token']}"}
        if role == "cashier":
            res = client.post(
                "/api/auth/login-pin",
                json={"pin_code": "2222", "device_id": TEST_DEVICE_ID},
            )
            assert res.status_code == 200, res.text
            return {"Authorization": f"Bearer {res.json()['access_token']}"}
        raise ValueError(f"Unknown role: {role}")

    return _get
