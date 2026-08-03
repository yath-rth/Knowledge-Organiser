import os
import sys
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta
import re
from email_reader import get_emails_from_last_24h
import firebase_admin
from firebase_admin import credentials, initialize_app, firestore

# Load environment variables
load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
DB_ID = os.getenv("DB_ID")
LM_STUDIO_URL = "http://localhost:1234"
LM_MODEL_NAME = os.getenv("LM_MODEL_NAME")
FIREBASE_CREDENTIAL_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")


def classify_email(email_item):
    """Sends a single email to LM Studio and parses JSON response"""

    system_prompt = (
        "You are an intelligent assistant. I will give you one email at a time. "
        "You must analyze it and return ONLY a valid JSON object with the following "
        "EXACT keys: 'type', 'title', 'date', 'time', 'priority', 'location', 'sender', "
        "'summary'. Do not include markdown formatting."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Email Details:\nFrom: {email_item['sender']}\n"
                f"Subject: {email_item['subject']}\n"
                f"Body: {email_item['body_preview']}\n\n"
                "Please extract the information into JSON format."
            ),
        },
    ]

    final_model_name = LM_MODEL_NAME if LM_MODEL_NAME else ""

    endpoint = f"{LM_STUDIO_URL}/v1/chat/completions"

    headers = {"Content-Type": "application/json"}

    payload = {
        "model": final_model_name,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1500,
    }

    print(f"Processing: {email_item['subject']}...")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=180)

        if response.status_code != 200:
            print(f"  Error from server ({response.status_code}): {response.text[:200]}")
            return None

        response_json = response.json()

        # Defensive access in case of malformed API response
        choices = response_json.get("choices")
        if not choices:
            print("  ERROR: No 'choices' in LM Studio response.")
            return None

        llm_response_text = choices[0]["message"]["content"]

        # Clean up potential markdown code blocks
        clean_json_str = re.sub(r'^```json\s*', '', llm_response_text, flags=re.MULTILINE)
        clean_json_str = re.sub(r'\s*```$', '', clean_json_str, flags=re.MULTILINE).strip()

        parsed_data = json.loads(clean_json_str)

        return {
            "type": parsed_data.get("type"),
            "title": parsed_data.get("title"),
            "date": parsed_data.get("date"),
            "time": parsed_data.get("time"),
            "priority": parsed_data.get("priority"),
            "location": parsed_data.get("location"),
            "sender": email_item["sender"],
            "summary": parsed_data.get("summary") or "",
            "raw_subject": email_item["subject"],  # Keep for reference in DB if needed
        }

    except json.JSONDecodeError:
        print("  WARNING: LLM returned invalid JSON. Skipping this email.")
        return None
    except (KeyError, IndexError) as e:
        print(f"  ERROR: Unexpected response structure from LM Studio: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: Request to LM Studio failed: {e}")
        return None
    except Exception as e:
        print(f"  ERROR processing email: {e}")
        return None


def save_to_firebase(data_list):
    """Saves the extracted emails to Firebase Firestore"""

    if not data_list:
        print("No data to save to Firebase.")
        return False

    try:
        # Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIAL_PATH)
            initialize_app(cred)

        db = firestore.client()  # FIXED: was firebase_admin.firestore()

        print(f"\nSaving {len(data_list)} emails to Firestore...")

        saved_count = 0
        for i, item in enumerate(data_list):
            # FIXED: datetime.datetime.now() -> datetime.now() (datetime already imported directly)
            doc_id = f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"

            try:
                db.collection("emails").document(doc_id).set(item)
                item_type = item.get("type") or "Unknown"
                print(f"  Saved: {item_type[:20]}...")
                saved_count += 1
            except Exception as e:
                print(f"  Failed to save doc {doc_id}: {e}")

        print(f"\nSuccessfully synced {saved_count}/{len(data_list)} emails to Firebase!")
        return saved_count > 0

    except Exception as e:
        print(f"\nCRITICAL ERROR connecting to Firebase: {e}")
        return False


def main():
    emails = get_emails_from_last_24h(EMAIL_USER, EMAIL_PASS)
    if not emails:
        print("No new emails found.")
        sys.exit(1)

    final_output_list = []
    errors_count = 0

    for i, email_item in enumerate(emails):
        print(f"\n[{i + 1}/{len(emails)}] Analyzing: {email_item['subject']}")

        result = classify_email(email_item)

        if result:
            final_output_list.append(result)
            print(f"  -> Extracted Type: {result.get('type', 'Unknown')}, "
                  f"Priority: {result.get('priority', 'N/A')}")
        else:
            errors_count += 1

    # Output to console (optional, for debugging)
    if final_output_list:
        print("\n" + "=" * 50)
        print(f"FINAL OUTPUT ({len(final_output_list)} items):")
        print("=" * 50)
        with open("extracted_emails_debug.json", "w") as f:
            json.dump(final_output_list, f, indent=2)
        print("Debug dump saved to 'extracted_emails_debug.json'")

    if errors_count:
        print(f"\n{errors_count} email(s) failed to process.")

    # Save to Firebase
    save_to_firebase(final_output_list)


if __name__ == "__main__":
    main()