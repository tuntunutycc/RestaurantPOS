"""CRUD tests for predefined instruction quick tags."""

from models import PredefinedInstruction
from services.predefined_instructions import DEFAULT_PREDEFINED_INSTRUCTIONS


def test_list_seeds_defaults(client, auth_headers):
    res = client.get("/api/predefined-instructions", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body) >= len(DEFAULT_PREDEFINED_INSTRUCTIONS)
    texts = {row["text"] for row in body}
    for default in DEFAULT_PREDEFINED_INSTRUCTIONS:
        assert default in texts


def test_admin_create_and_delete(client, auth_headers, db_session):
    create = client.post(
        "/api/predefined-instructions",
        headers=auth_headers("admin"),
        json={"text": "No Cilantro"},
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["text"] == "No Cilantro"

    listed = client.get("/api/predefined-instructions", headers=auth_headers("waiter"))
    assert listed.status_code == 200
    assert any(row["id"] == created["id"] for row in listed.json())

    delete = client.delete(
        f"/api/predefined-instructions/{created['id']}",
        headers=auth_headers("admin"),
    )
    assert delete.status_code == 200, delete.text

    row = db_session.query(PredefinedInstruction).filter(PredefinedInstruction.id == created["id"]).first()
    assert row is None


def test_duplicate_text_rejected(client, auth_headers):
    first = client.post(
        "/api/predefined-instructions",
        headers=auth_headers("admin"),
        json={"text": "Extra Hot"},
    )
    assert first.status_code == 200, first.text

    dup = client.post(
        "/api/predefined-instructions",
        headers=auth_headers("admin"),
        json={"text": "Extra Hot"},
    )
    assert dup.status_code == 400, dup.text


def test_waiter_cannot_create(client, auth_headers):
    res = client.post(
        "/api/predefined-instructions",
        headers=auth_headers("waiter"),
        json={"text": "Should Fail"},
    )
    assert res.status_code == 403, res.text


def test_waiter_cannot_delete(client, auth_headers, db_session):
    row = PredefinedInstruction(text="Delete Me Tag")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    res = client.delete(
        f"/api/predefined-instructions/{row.id}",
        headers=auth_headers("waiter"),
    )
    assert res.status_code == 403, res.text
