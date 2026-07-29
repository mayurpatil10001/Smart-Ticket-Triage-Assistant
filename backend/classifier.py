"""
classifier.py — LLM-powered intent classifier.

Calls the Google Gemini API to classify a support ticket into one of:
    password_reset | login_failure | leave_balance_inquiry | unclassified

Returns
-------
dict with keys:
    intent      str    — one of the four labels above
    confidence  float  — 0.0–1.0
    entities    dict   — extracted named entities (e.g. {"username": "john"})

Falls back to `unclassified` when:
    - The LLM returns confidence < 0.6
    - The API key is missing / the call fails
"""

import json
import logging
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

VALID_INTENTS = {
    "password_reset",
    "login_failure",
    "leave_balance_inquiry",
    "unclassified",
}

SYSTEM_PROMPT = """You are a support-ticket classifier for an internal HR/IT helpdesk.
Classify the user's ticket into EXACTLY ONE of these intents:
  - password_reset        : user wants to reset or recover their password
  - login_failure         : user cannot log in (may or may not know the cause)
  - leave_balance_inquiry : user wants to know their leave / vacation balance
  - unclassified          : does not fit any category above

Also extract any named entities (e.g. username, error code, dates).

Respond ONLY with a valid JSON object — no markdown, no prose — in this exact shape:
{
  "intent": "<one of the four labels>",
  "confidence": <float between 0 and 1>,
  "entities": { <key-value pairs or empty object> }
}

Rules:
- If confidence < 0.6 for all known intents, set intent to "unclassified".
- Never invent new intent labels.
"""


def classify_ticket(text: str) -> dict:
    """
    Classify a support ticket using the Gemini LLM.

    If no API key is configured the function falls back to a rule-based
    heuristic so the service still works during local development without
    credentials.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not set — using heuristic fallback classifier")
        return _heuristic_classify(text)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_PROMPT}\n\n"
                            f"Support ticket:\n\"\"\"\n{text}\n\"\"\""
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 256,
        },
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_text = (
            data["candidates"][0]["content"]["parts"][0]["text"].strip()
        )
        # Strip any accidental markdown fences
        raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text)
        result = json.loads(raw_text)
        return _validate_result(result)
    except Exception as exc:
        logger.error("Classifier LLM call failed: %s — falling back to heuristic", exc)
        return _heuristic_classify(text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_result(result: dict) -> dict:
    intent = result.get("intent", "unclassified")
    if intent not in VALID_INTENTS:
        intent = "unclassified"

    confidence = float(result.get("confidence", 0.0))
    if confidence < 0.6:
        intent = "unclassified"

    return {
        "intent": intent,
        "confidence": round(confidence, 4),
        "entities": result.get("entities", {}),
    }


def _heuristic_classify(text: str) -> dict:
    """
    Simple keyword-based fallback classifier used when no API key is present.
    Intentionally conservative — prefers `unclassified` when uncertain.
    """
    lower = text.lower()

    # password_reset signals
    if any(k in lower for k in ["forgot password", "reset password", "reset my password",
                                  "forgot my password", "recover password"]):
        return {"intent": "password_reset", "confidence": 0.92, "entities": {}}

    # login_failure signals (must come after password_reset to avoid overlap
    # with "password is incorrect" which is more login_failure than reset)
    if any(k in lower for k in ["can't log in", "cannot log in", "can't login",
                                  "cannot login", "unable to log", "login failed",
                                  "password is incorrect", "incorrect password",
                                  "sign in", "signin"]):
        return {"intent": "login_failure", "confidence": 0.88, "entities": {}}

    # leave_balance signals
    if any(k in lower for k in ["leave balance", "vacation balance", "pto balance",
                                  "annual leave", "sick leave", "days off",
                                  "remaining leave", "how many leaves",
                                  "see leave", "check leave"]):
        return {"intent": "leave_balance_inquiry", "confidence": 0.91, "entities": {}}

    return {"intent": "unclassified", "confidence": 0.30, "entities": {}}
