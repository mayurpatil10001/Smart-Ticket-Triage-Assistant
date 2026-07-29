"""
stubs.py — Stub implementations of external integrations.

Each function is clearly marked as a STUB so it can be replaced with a real
integration (SendGrid, Workday HR API, Active Directory, etc.) later.
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Email / identity stubs
# ---------------------------------------------------------------------------


def send_reset_email(user_id: str) -> dict:
    """
    STUB — Replace with real email provider (SendGrid, AWS SES, Mailgun …).

    Should send a password-reset link to the email address associated with
    `user_id`.  Returns a dict that mirrors what a real provider would return
    (e.g. a message ID and delivery status).
    """
    logger.info("[STUB] send_reset_email called for user_id=%s", user_id)
    return {
        "stub": True,
        "status": "queued",
        "message_id": f"stub-msg-{user_id}-reset",
        "to": f"{user_id}@example.com",
    }


def unlock_account(user_id: str) -> dict:
    """
    STUB — Replace with real account-management system (Active Directory,
    Okta, Auth0 Management API …).

    Should unlock the account and optionally force a password reset on next
    login.
    """
    logger.info("[STUB] unlock_account called for user_id=%s", user_id)
    return {
        "stub": True,
        "status": "unlocked",
        "user_id": user_id,
    }


# ---------------------------------------------------------------------------
# HR system stubs
# ---------------------------------------------------------------------------


def get_leave_balance(user_id: str) -> dict:
    """
    STUB — Replace with real HR system API (Workday, BambooHR, SAP SuccessFactors …).

    Should return the current leave balance for the employee identified by
    `user_id`, broken down by leave type.
    """
    logger.info("[STUB] get_leave_balance called for user_id=%s", user_id)
    # Deterministic fake values so tests are reproducible
    return {
        "stub": True,
        "user_id": user_id,
        "annual_leave": 12,
        "sick_leave": 7,
        "casual_leave": 3,
        "total_remaining": 22,
    }
