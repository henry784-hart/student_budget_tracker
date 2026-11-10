import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def make_tx(**overrides):
    data = {
        "amount": 100,
        "type": "expense",
        "category": "Food",
        "note": "",
        "date": "2026-11-10",
    }
    data.update(overrides)
    return data


# --- health ---------------------------------------------------------------


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "running" in response.get_json()["message"]


# --- transactions ---------------------------------------------------------


def test_create_and_list(client):
    response = client.post("/api/transactions", json=make_tx())
    assert response.status_code == 201
    created = response.get_json()
    assert created["amount"] == 100
    assert created["id"] > 0

    listed = client.get("/api/transactions").get_json()
    assert len(listed) == 1
    assert listed[0]["category"] == "Food"


def test_list_is_newest_first(client):
    client.post("/api/transactions", json=make_tx(date="2026-11-01"))
    client.post("/api/transactions", json=make_tx(date="2026-11-09"))
    dates = [t["date"] for t in client.get("/api/transactions").get_json()]
    assert dates == ["2026-11-09", "2026-11-01"]


def test_rejects_bad_amount(client):
    assert client.post("/api/transactions", json=make_tx(amount=-5)).status_code == 400
    assert client.post("/api/transactions", json=make_tx(amount=0)).status_code == 400
    assert client.post("/api/transactions", json=make_tx(amount="abc")).status_code == 400


def test_rejects_bad_type(client):
    assert client.post("/api/transactions", json=make_tx(type="gift")).status_code == 400


def test_rejects_missing_category(client):
    assert client.post("/api/transactions", json=make_tx(category="  ")).status_code == 400


def test_rejects_bad_date(client):
    assert client.post("/api/transactions", json=make_tx(date="10/11/2026")).status_code == 400


def test_rejects_empty_body(client):
    assert client.post("/api/transactions", json={}).status_code == 400


def test_update_transaction(client):
    tx_id = client.post("/api/transactions", json=make_tx()).get_json()["id"]
    response = client.put(
        f"/api/transactions/{tx_id}",
        json=make_tx(amount=75, type="income", category="Job", note="raise"),
    )
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["amount"] == 75
    assert updated["type"] == "income"
    assert updated["note"] == "raise"


def test_update_missing_transaction(client):
    assert client.put("/api/transactions/999", json=make_tx()).status_code == 404


def test_delete_transaction(client):
    tx_id = client.post("/api/transactions", json=make_tx()).get_json()["id"]
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 200
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 404
    assert client.get("/api/transactions").get_json() == []


# --- budget ---------------------------------------------------------------


def test_budget_defaults_to_zero(client):
    data = client.get("/api/budget?month=2026-11").get_json()
    assert data == {"month": "2026-11", "limit": 0}


def test_set_and_read_budget(client):
    response = client.put("/api/budget", json={"month": "2026-11", "limit": 5000})
    assert response.status_code == 200
    assert response.get_json()["limit"] == 5000

    assert client.get("/api/budget?month=2026-11").get_json()["limit"] == 5000


def test_budget_update_overwrites(client):
    client.put("/api/budget", json={"month": "2026-11", "limit": 5000})
    client.put("/api/budget", json={"month": "2026-11", "limit": 8000})
    assert client.get("/api/budget?month=2026-11").get_json()["limit"] == 8000


def test_budget_rejects_bad_values(client):
    assert client.put("/api/budget", json={"month": "2026-11", "limit": 0}).status_code == 400
    assert client.put("/api/budget", json={"month": "2026-11", "limit": "x"}).status_code == 400
    assert client.put("/api/budget", json={"month": "Nov 2026", "limit": 100}).status_code == 400


# --- M-Pesa parser --------------------------------------------------------


def test_parse_paid_to(client):
    message = (
        "QGH4XYZ12A Confirmed. Ksh250.00 paid to JAVA HOUSE on 10/11/26 at 1:24 PM."
    )
    data = client.post("/api/transactions/parse", json={"message": message}).get_json()
    assert data["amount"] == 250
    assert data["type"] == "expense"
    assert data["category"] == "Food"
    assert data["date"] == "2026-11-10"
    assert data["code"] == "QGH4XYZ12A"


def test_parse_received_from_is_income(client):
    message = (
        "RKT9QW2LMP Confirmed. Ksh1,500.00 received from 254712345678 JOHN DOE "
        "on 9/11/26 at 8:02 AM."
    )
    data = client.post("/api/transactions/parse", json={"message": message}).get_json()
    assert data["amount"] == 1500
    assert data["type"] == "income"
    assert data["date"] == "2026-11-09"


def test_parse_sent_to_transport(client):
    message = (
        "ABC1234567 Confirmed. Ksh60.00 sent to MATATU SACCO on 10/11/26 at 6:45 AM."
    )
    data = client.post("/api/transactions/parse", json={"message": message}).get_json()
    assert data["category"] == "Transport"
    assert data["type"] == "expense"


def test_parse_unknown_party_is_other(client):
    message = (
        "XYZ9876543 Confirmed. Ksh300.00 paid to 123456 SOME SHOP on 10/11/26 at 2:00 PM."
    )
    data = client.post("/api/transactions/parse", json={"message": message}).get_json()
    assert data["category"] == "Other"


def test_parse_rejects_garbage(client):
    assert client.post("/api/transactions/parse", json={"message": "hello"}).status_code == 400
    assert client.post("/api/transactions/parse", json={"message": ""}).status_code == 400
