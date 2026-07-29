"""
response_handler.py — Generates intent-appropriate responses for each ticket.

Branching logic
---------------
password_reset        → mock send_reset_email() + return templated instructions
login_failure         → return clarifying question (two-step flow)
leave_balance_inquiry → call get_leave_balance(user_id) stub + natural sentence
unclassified          → no auto-response; ticket marked for human review
"""

import logging
from typing import Optional

from stubs import get_leave_balance, send_reset_email, unlock_account

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_RESET_TEMPLATE = """\
Hi there,

We've received your request to reset your password. Here's what happens next:

1. A password-reset link has been sent to your registered email address.
2. Click the link within 30 minutes — it will expire after that.
3. Choose a new password that is at least 8 characters long and includes
   a mix of letters, numbers, and symbols.
4. If you don't receive the email within a few minutes, please check your
   spam/junk folder.

If you continue to have trouble, reply to this ticket and our support team
will assist you directly.

— IT Helpdesk Bot 🤖\
"""

_LOGIN_CLARIFY_TEMPLATE = """\
Sorry to hear you're having trouble logging in! Before we can help, could you
let us know a bit more:

**Did you forget your password**, or do you think your **account might be
locked** (e.g., too many failed login attempts)?

Please reply with one of:
  • "I forgot my password"
  • "I think my account is locked"

We'll take it from there right away! 🙂\
"""

_ACCOUNT_UNLOCK_TEMPLATE = """\
Your account has been unlocked.

Here's what to do next:

1. Try logging in again now — your account is active.
2. If you're also having trouble remembering your password, reply and we'll
   send you a reset link.
3. To avoid future lockouts, remember that accounts are locked after
   5 consecutive failed login attempts.

— IT Helpdesk Bot 🤖\
"""

_UNCLASSIFIED_TEMPLATE = """\
Thank you for reaching out. Your ticket has been received and flagged for
review by a human support agent.

A member of our team will get back to you shortly. In the meantime, if you
have any additional context to share, feel free to reply to this ticket.

— IT Helpdesk Bot 🤖\
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_response(
    intent: str,
    user_id: str,
    entities: Optional[dict] = None,
) -> tuple[str, str]:
    """
    Build an auto-response for the given intent.

    Returns
    -------
    (response_text, status)
        response_text : str  — the message shown/sent to the user
        status        : str  — 'open' | 'needs_human_review'
    """
    entities = entities or {}

    if intent == "password_reset":
        return _handle_password_reset(user_id)
    elif intent == "login_failure":
        return _handle_login_failure(user_id)
    elif intent == "leave_balance_inquiry":
        return _handle_leave_balance(user_id)
    else:
        return _handle_unclassified()


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


def _handle_password_reset(user_id: str) -> tuple[str, str]:
    result = send_reset_email(user_id)
    logger.info("Password reset email stub result: %s", result)
    return _RESET_TEMPLATE, "open"


def _handle_login_failure(user_id: str) -> tuple[str, str]:
    """
    First step of the two-step login-failure flow.

    We ask a clarifying question. The ticket status stays 'open' while we
    wait for the user's reply. A real implementation would track conversation
    state (e.g. in Redis or a sessions table) so the follow-up reply can be
    routed to _handle_password_reset or _handle_account_unlock accordingly.

    For this prototype the clarifying question is the auto-response.
    """
    return _LOGIN_CLARIFY_TEMPLATE, "open"


def handle_login_failure_followup(user_id: str, reply: str) -> tuple[str, str]:
    """
    Second step: processes the user's answer to the clarifying question.

    Called by a route that accepts follow-up replies (not wired to /tickets
    in this prototype, but exported so it can be integrated easily).
    """
    lower = reply.lower()
    if any(k in lower for k in ["forgot", "reset", "password", "remember"]):
        return _handle_password_reset(user_id)
    elif any(k in lower for k in ["locked", "lock", "blocked", "suspended"]):
        result = unlock_account(user_id)
        logger.info("Account unlock stub result: %s", result)
        return _ACCOUNT_UNLOCK_TEMPLATE, "open"
    else:
        # Can't determine — escalate
        return _UNCLASSIFIED_TEMPLATE, "needs_human_review"


def _handle_leave_balance(user_id: str) -> tuple[str, str]:
    balance = get_leave_balance(user_id)
    logger.info("Leave balance stub result: %s", balance)
    total = balance["total_remaining"]
    annual = balance["annual_leave"]
    sick = balance["sick_leave"]
    casual = balance["casual_leave"]
    text = (
        f"Hi! Here's your current leave balance:\n\n"
        f"  🗓  Annual leave  : {annual} days\n"
        f"  🤒  Sick leave    : {sick} days\n"
        f"  ☀️  Casual leave  : {casual} days\n"
        f"  ─────────────────────────\n"
        f"  ✅  Total remaining: **{total} days**\n\n"
        f"If you need to apply for leave, please use the HR portal or reply "
        f"to this ticket and we'll guide you through the process.\n\n"
        f"— IT Helpdesk Bot 🤖"
    )
    return text, "open"


def _handle_unclassified() -> tuple[str, str]:
    return _UNCLASSIFIED_TEMPLATE, "needs_human_review"
