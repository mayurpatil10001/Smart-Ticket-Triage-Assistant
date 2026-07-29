import requests
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"

tickets = [
    ("a. Password Reset", "I forgot my password, how to reset it?", "user-001"),
    ("b. Login Failure", "I can't log in, as password is incorrect.", "user-002"),
    ("c. Leave Balance", "How to see leave balance?", "user-003"),
    ("d. Edge Case (Invoice)", "Why is my invoice wrong?", "user-004")
]

print("="*80)
print("VERIFYING BACKEND /tickets ENDPOINT WITH ALL 4 TEST TICKETS")
print("="*80)

for label, text, user_id in tickets:
    print(f"\n--- [TEST] {label} ---")
    print(f"Input Text : \"{text}\"")
    print(f"User ID    : {user_id}")
    
    resp = requests.post(f"{BASE_URL}/tickets", json={"text": text, "user_id": user_id})
    print(f"HTTP Status: {resp.status_code}")
    if resp.status_code == 201:
        data = resp.json()
        print(f"Classified Intent: {data['classification']['intent']} (Confidence: {data['classification']['confidence']})")
        print(f"Status           : {data['status']}")
        print(f"Response Preview :\n{data['response']}")
    else:
        print(f"Error: {resp.text}")
    print("-" * 60)

print("\n" + "="*80)
print("VERIFYING GET /tickets/escalated ENDPOINT")
print("="*80)
resp_esc = requests.get(f"{BASE_URL}/tickets/escalated")
print(f"HTTP Status: {resp_esc.status_code}")
print(json.dumps(resp_esc.json(), indent=2))
