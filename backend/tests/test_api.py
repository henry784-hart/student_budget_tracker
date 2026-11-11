import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402


@pytest.fixture
def anon(tmp_path, monkeypatch):
    """A client that is not signed in, against a fresh database."""
    monkeypatch.setattr(app_module, "DB_PATH", str(tmp_path / "test.db"))
    app_module.app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )
    app_module.init_db()
    app_module._rate_events.clear()   # every test starts with fresh counters
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def client(anon):
    """A client signed in as the first test user."""
    response = anon.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "s3cure-pass"},
    )
    assert response.status_code == 201
    return anon


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


def test_health(anon):
    response = anon.get("/")
    assert response.status_code == 200
    assert "running" in response.get_json()["message"]


# --- accounts / auth -------------------------------------------------------


def test_register_signs_user_in(client):
    data = client.get("/api/auth/me").get_json()
    assert data["email"] == "student@example.com"


def test_register_rejects_bad_email(anon):
    assert anon.post("/api/auth/register",
                     json={"email": "not-an-email", "password": "s3cure-pass"}).status_code == 400


def test_register_rejects_short_password(anon):
    assert anon.post("/api/auth/register",
                     json={"email": "a@b.co", "password": "short"}).status_code == 400


def test_register_rejects_duplicate_email(anon):
    body = {"email": "dup@example.com", "password": "s3cure-pass"}
    assert anon.post("/api/auth/register", json=body).status_code == 201
    anon.post("/api/auth/logout")
    assert anon.post("/api/auth/register", json=body).status_code == 409


def test_login_and_logout(anon):
    anon.post("/api/auth/register",
              json={"email": "me@example.com", "password": "s3cure-pass"})
    anon.post("/api/auth/logout")
    assert anon.get("/api/auth/me").status_code == 401

    assert anon.post("/api/auth/login",
                     json={"email": "me@example.com", "password": "s3cure-pass"}).status_code == 200
    assert anon.get("/api/auth/me").status_code == 200


def test_login_rejects_wrong_password(anon):
    anon.post("/api/auth/register",
              json={"email": "me@example.com", "password": "s3cure-pass"})
    anon.post("/api/auth/logout")
    response = anon.post("/api/auth/login",
                         json={"email": "me@example.com", "password": "wrong-pass"})
    assert response.status_code == 401
    assert "wrong email or password" in response.get_json()["error"].lower()


def test_login_unknown_email_says_same_thing(anon):
    response = anon.post("/api/auth/login",
                         json={"email": "nobody@example.com", "password": "whatever1"})
    assert response.status_code == 401
    assert "wrong email or password" in response.get_json()["error"].lower()


def test_password_is_hashed(anon):
    anon.post("/api/auth/register",
              json={"email": "hash@example.com", "password": "s3cure-pass"})
    conn = app_module.get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE email = ?",
                       ("hash@example.com",)).fetchone()
    conn.close()
    assert row["password_hash"] != "s3cure-pass"
    assert "s3cure-pass" not in row["password_hash"]


def test_logout_clears_session(client):
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/transactions").status_code == 401
    assert client.get("/api/auth/me").status_code == 401

def test_register_is_rate_limited(anon):
    limit = app_module.RATE_LIMIT_LOGIN_PER_IP
    for i in range(limit):
        response = anon.post(
            "/api/auth/register",
            json={"email": f"user{i}@example.com", "password": "s3cure-pass"},
        )
        assert response.status_code == 201
    response = anon.post(
        "/api/auth/register",
        json={"email": "one-too-many@example.com", "password": "s3cure-pass"},
    )
    assert response.status_code == 429


def test_login_is_rate_limited_per_email(anon):
    anon.post("/api/auth/register",
              json={"email": "me@example.com", "password": "s3cure-pass"})
    anon.post("/api/auth/logout")
    for _ in range(app_module.RATE_LIMIT_LOGIN_PER_EMAIL):
        wrong = anon.post("/api/auth/login",
                          json={"email": "me@example.com", "password": "wrong-pass"})
        assert wrong.status_code == 401
    # Even the correct password is refused once the account is locked out.
    right = anon.post("/api/auth/login",
                      json={"email": "me@example.com", "password": "s3cure-pass"})
    assert right.status_code == 429

    
# --- unauthenticated access ------------------------------------------------


def test_requires_login_for_every_data_route(anon):
    assert anon.get("/api/transactions").status_code == 401
    assert anon.post("/api/transactions", json=make_tx()).status_code == 401
    assert anon.put("/api/transactions/1", json=make_tx()).status_code == 401
    assert anon.delete("/api/transactions/1").status_code == 401
    assert anon.get("/api/budget").status_code == 401
    assert anon.put("/api/budget", json={"limit": 10}).status_code == 401
    assert anon.post("/api/transactions/parse", json={"message": "x"}).status_code == 401
    assert anon.get("/api/auth/me").status_code == 401


# --- user isolation --------------------------------------------------------


def test_users_cannot_see_each_others_transactions(client):
    client.post("/api/transactions", json=make_tx(category="Mine"))

    other = app_module.app.test_client()
    other.post("/api/auth/register",
               json={"email": "other@example.com", "password": "s3cure-pass"})
    assert other.get("/api/transactions").get_json() == []

    other.post("/api/transactions", json=make_tx(category="Theirs"))
    mine = client.get("/api/transactions").get_json()
    assert [t["category"] for t in mine] == ["Mine"]


def test_users_cannot_edit_or_delete_another_users_transaction(client):
    victim_id = client.post("/api/transactions", json=make_tx()).get_json()["id"]

    other = app_module.app.test_client()
    other.post("/api/auth/register",
               json={"email": "other@example.com", "password": "s3cure-pass"})

    assert other.put(f"/api/transactions/{victim_id}",
                     json=make_tx(amount=1)).status_code == 404
    assert other.delete(f"/api/transactions/{victim_id}").status_code == 404

    # The victim's row is untouched.
    still_there = client.get("/api/transactions").get_json()
    assert len(still_there) == 1 and still_there[0]["amount"] == 100


def test_budgets_are_per_user(client):
    client.put("/api/budget", json={"month": "2026-11", "limit": 5000})

    other = app_module.app.test_client()
    other.post("/api/auth/register",
               json={"email": "other@example.com", "password": "s3cure-pass"})
    assert other.get("/api/budget?month=2026-11").get_json()["limit"] == 0

    other.put("/api/budget", json={"month": "2026-11", "limit": 900})
    assert client.get("/api/budget?month=2026-11").get_json()["limit"] == 5000


# --- transactions ---------------------------------------------------------


def test_create_and_list(client):
    response = client.post("/api/transactions", json=make_tx())
    assert response.status_code == 201
    created = response.get_json()
    assert created["amount"] == 100
    assert created["id"] > 0
    assert "user_id" not in created

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


def test_rejects_nan_and_infinity(client):
    for bad in ("nan", "inf", "-inf", "NaN", "Infinity"):
        assert client.post("/api/transactions", json=make_tx(amount=bad)).status_code == 400


def test_rejects_absurd_amount(client):
    assert client.post("/api/transactions", json=make_tx(amount=1e300)).status_code == 400


def test_amount_is_rounded(client):
    created = client.post("/api/transactions", json=make_tx(amount=10.239)).get_json()
    assert created["amount"] == 10.24


def test_rejects_oversized_fields(client):
    assert client.post("/api/transactions",
                       json=make_tx(category="x" * 41)).status_code == 400
    assert client.post("/api/transactions",
                       json=make_tx(note="y" * 201)).status_code == 400


def test_rejects_oversized_body(client):
    huge = '{"amount": 10, "type": "expense", "category": "Food", ' \
           '"date": "2026-11-10", "note": "' + "y" * 200_000 + '"}'
    response = client.post("/api/transactions", data=huge,
                           content_type="application/json")
    assert response.status_code == 413


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
    assert client.put("/api/budget", json={"month": "2026-11", "limit": "nan"}).status_code == 400


def test_budget_rejects_delete(client):
    assert client.post("/api/budget", json={"limit": 1}).status_code == 405


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
    assert client.post("/api/transactions/parse",
                       json={"message": "x" * 5000}).status_code == 400


# --- misc security --------------------------------------------------------


def test_unknown_api_route_returns_json(anon):
    response = anon.get("/no-such-page")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_cors_preflight_is_not_blocked_by_login(anon):
    origin = "http://127.0.0.1:5500"
    response = anon.options("/api/transactions", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code < 400
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_rejects_unknown_origin(anon):
    response = anon.get("/api/transactions", headers={"Origin": "https://evil.example"})
    assert response.headers.get("Access-Control-Allow-Origin") is None


def test_production_missing_secret_key_fails_loudly(tmp_path):
    """A real host must not silently rotate the session key on every restart."""
    import subprocess

    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    env["RENDER"] = "true"
    env["DB_PATH"] = str(tmp_path / "prod.db")
    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "SECRET_KEY is not set" in result.stderr


def test_security_headers(anon):
    headers = anon.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
