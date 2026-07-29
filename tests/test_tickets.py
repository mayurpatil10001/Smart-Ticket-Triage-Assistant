"""
test_tickets.py — Pytest suite for the Smart Ticket Triage Assistant.

Test matrix
-----------
ID  | Input ticket                               | Expected intent          | Expected response type
----|--------------------------------------------|--------------------------|-----------------------
T1  | "I forgot my password, how to reset it?"   | password_reset           | templated reset instructions
T2  | "I can't log in, as password is incorrect."| login_failure            | clarifying question
T3  | "How to see leave balance?"                | leave_balance_inquiry    | natural sentence with balance
T4  | "Why is my invoice wrong?"                 | unclassified             | needs_human_review status

The LLM (classifier.classify_ticket) is monkeypatched so tests run fully
offline without consuming any API credits.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── Path setup ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import database  # noqa: E402

# Redirect SQLite to a temp file so tests never touch production data
_tmp_dir = tempfile.mkdtemp()
database.DB_PATH = Path(_tmp_dir) / "test_tickets.db"

# Import app AFTER patching DB_PATH
from main import app  # noqa: E402

# ── Mock LLM responses ───────────────────────────────────────────────────────
_MOCK_CLASSIFICATIONS = {
    "forgot my password": {"intent": "password_reset",        "confidence": 0.97, "entities": {}},
    "can't log in":       {"intent": "login_failure",         "confidence": 0.91, "entities": {}},
    "password is incorrect": {"intent": "login_failure",      "confidence": 0.89, "entities": {}},
    "leave balance":      {"intent": "leave_balance_inquiry", "confidence": 0.95, "entities": {}},
    "invoice":            {"intent": "unclassified",          "confidence": 0.28, "entities": {}},
}


def _fake_classify(text: str) -> dict:
    lower = text.lower()
    for keyword, result in _MOCK_CLASSIFICATIONS.items():
        if keyword in lower:
            return result
    return {"intent": "unclassified", "confidence": 0.20, "entities": {}}


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """
    Session-scoped TestClient.  Using `with TestClient(app)` enters the
    lifespan context manager, which calls database.init_db() before any
    request is made.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def patch_classifier():
    """Patch the LLM call so all tests run offline."""
    with patch("routes.tickets.classify_ticket", side_effect=_fake_classify):
        yield


# ── T1 — Password Reset ───────────────────────────────────────────────────────

class TestPasswordReset:
    """T1 — 'I forgot my password, how to reset it?'"""

    _TICKET = {"text": "I forgot my password, how to reset it?", "user_id": "user-001"}

    def test_intent_is_password_reset(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.status_code == 201
        assert resp.json()["classification"]["intent"] == "password_reset"

    def test_confidence_above_threshold(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.json()["classification"]["confidence"] >= 0.6

    def test_response_contains_reset_instructions(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        data = resp.json()
        text = data["response"].lower()
        assert "reset" in text
        assert "email" in text
        assert data["status"] == "open"

    def test_ticket_is_persisted(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        ticket_id = resp.json()["id"]
        all_ids = [t["id"] for t in client.get("/tickets").json()["tickets"]]
        assert ticket_id in all_ids


# ── T2 — Login Failure ────────────────────────────────────────────────────────

class TestLoginFailure:
    """T2 — 'I can't log in, as password is incorrect.'"""

    _TICKET = {"text": "I can't log in, as password is incorrect.", "user_id": "user-002"}

    def test_intent_is_login_failure(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.status_code == 201
        assert resp.json()["classification"]["intent"] == "login_failure"

    def test_response_is_clarifying_question(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        text = resp.json()["response"].lower()
        assert "forgot" in text or "forget" in text or "locked" in text
        assert "?" in resp.json()["response"]

    def test_status_is_open(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.json()["status"] == "open"


# ── T3 — Leave Balance Inquiry ────────────────────────────────────────────────

class TestLeaveBalanceInquiry:
    """T3 — 'How to see leave balance?'"""

    _TICKET = {"text": "How to see leave balance?", "user_id": "user-003"}

    def test_intent_is_leave_balance_inquiry(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.status_code == 201
        assert resp.json()["classification"]["intent"] == "leave_balance_inquiry"

    def test_response_contains_balance_data(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        text = resp.json()["response"].lower()
        assert "leave" in text
        assert any(ch.isdigit() for ch in text)

    def test_response_is_natural_sentence(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        response = resp.json()["response"]
        assert len(response) > 50
        assert "{" not in response  # no raw JSON bleed-through


# ── T4 — Unclassified (edge case) ─────────────────────────────────────────────

class TestUnclassified:
    """T4 — 'Why is my invoice wrong?' — should escalate to human review."""

    _TICKET = {"text": "Why is my invoice wrong?", "user_id": "user-004"}

    def test_intent_is_unclassified(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.status_code == 201
        assert resp.json()["classification"]["intent"] == "unclassified"

    def test_status_is_needs_human_review(self, client):
        resp = client.post("/tickets", json=self._TICKET)
        assert resp.json()["status"] == "needs_human_review"

    def test_appears_in_escalated_endpoint(self, client):
        post_resp = client.post("/tickets", json=self._TICKET)
        ticket_id = post_resp.json()["id"]

        esc_resp = client.get("/tickets/escalated")
        assert esc_resp.status_code == 200
        escalated_ids = [t["id"] for t in esc_resp.json()["tickets"]]
        assert ticket_id in escalated_ids

    def test_escalated_count_increases(self, client):
        initial = client.get("/tickets/escalated").json()["count"]
        client.post("/tickets", json=self._TICKET)
        after = client.get("/tickets/escalated").json()["count"]
        assert after == initial + 1


# ── API contract ──────────────────────────────────────────────────────────────

class TestAPIContract:

    def test_missing_text_returns_422(self, client):
        assert client.post("/tickets", json={"user_id": "user-x"}).status_code == 422

    def test_missing_user_id_returns_422(self, client):
        assert client.post("/tickets", json={"text": "Hello"}).status_code == 422

    def test_empty_text_returns_422(self, client):
        assert client.post("/tickets", json={"text": "", "user_id": "user-x"}).status_code == 422

    def test_response_has_required_fields(self, client):
        resp = client.post(
            "/tickets",
            json={"text": "I forgot my password", "user_id": "user-001"},
        )
        data = resp.json()
        for field in ("id", "text", "user_id", "classification", "response", "status", "created_at"):
            assert field in data, f"Missing field: {field}"

    def test_health_check(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
