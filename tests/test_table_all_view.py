"""Table grid ALL view: API returns full multi-zone table sets without pagination."""

import uuid

from models import Table, Zone


def _seed_zones_with_tables(db_session):
    suffix = uuid.uuid4().hex[:6]
    zone_a = Zone(name=f"Zone-A-{suffix}")
    zone_b = Zone(name=f"Zone-B-{suffix}")
    db_session.add_all([zone_a, zone_b])
    db_session.flush()
    tables = [
        Table(name_or_number=f"Table G{i}-{suffix}", zone_id=zone_a.id, status="available")
        for i in range(1, 4)
    ] + [
        Table(name_or_number=f"F{i}-{suffix}", zone_id=zone_b.id, status="available")
        for i in range(1, 4)
    ]
    db_session.add_all(tables)
    db_session.commit()
    return zone_a, zone_b, tables


def test_tables_grid_returns_all_zones_and_tables(client, auth_headers, db_session):
    zone_a, zone_b, tables = _seed_zones_with_tables(db_session)

    res = client.get("/api/tables/grid", headers=auth_headers("waiter"))
    assert res.status_code == 200, res.text
    payload = res.json()
    assert len(payload) >= 2

    zone_ids = {z["id"] for z in payload}
    assert zone_a.id in zone_ids
    assert zone_b.id in zone_ids

    all_table_ids = {t["id"] for z in payload for t in z.get("tables", [])}
    for table in tables:
        assert table.id in all_table_ids


def test_tables_status_returns_all_zones_and_tables(client, auth_headers, db_session):
    zone_a, zone_b, tables = _seed_zones_with_tables(db_session)

    res = client.get("/api/tables/status", headers=auth_headers("cashier"))
    assert res.status_code == 200, res.text
    payload = res.json()
    assert len(payload) >= 2

    all_table_ids = {t["id"] for z in payload for t in z.get("tables", [])}
    for table in tables:
        assert table.id in all_table_ids

    names = {t["name"] for z in payload for t in z.get("tables", [])}
    assert tables[0].name_or_number in names
