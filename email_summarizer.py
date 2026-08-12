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
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234")
LM_MODEL_NAME = os.getenv("LM_MODEL_NAME")
FIREBASE_CREDENTIAL_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "service_account.json")
STUDENT_NAMES = [n.strip() for n in os.getenv("STUDENT_NAME", "").split(",") if n.strip()]
STUDENT_REGNOS = [r.strip() for r in os.getenv("STUDENT_REGNO", "").split(",") if r.strip()]

def summarize_excel_match(email_item, filename, chunk_text, matched_term, chunk_index, total_chunks):
    """
    Called only on a chunk that already matched the student's name/regno.
    Asks the LLM to describe what this list/sheet actually is, so the
    email summary can say e.g. "You are shortlisted for Round 2 of X".
    """
    system_prompt = """
You are looking at a chunk of rows from an Excel attachment. The
student's name or registration number was found in this chunk via
exact string match. Your job is only to describe what this sheet
appears to be about, using the surrounding row/column context.

Return ONLY a valid JSON object:
{
  "context": "short description of what this list/sheet is (e.g. 'Round 2 interview shortlist for Company X')"
}

Do not invent information you cannot see in the data.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Email Subject: {email_item['subject']}\n"
                f"Attachment: {filename} (chunk {chunk_index + 1}/{total_chunks})\n"
                f"Matched term: {matched_term}\n\n"
                f"{chunk_text}\n\n"
                "What is this sheet about? Respond with JSON only."
            ),
        },
    ]

    payload = {
        "model": LM_MODEL_NAME or "",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 300,
    }

    try:
        response = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        if response.status_code != 200:
            print(f"    Context summary error: {response.status_code}")
            return "Match found, but could not summarize context."

        content = response.json()["choices"][0]["message"]["content"]
        clean = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE).strip()
        parsed = json.loads(clean)
        return parsed.get("context") or "Match found, context unclear."

    except Exception as e:
        print(f"    Context summary failed: {e}")
        return "Match found, but could not summarize context."

def normalize_summary(summary_text):
    """
    Ensures summary is bullet-formatted even if the LLM didn't comply.
    If it already looks bulleted, leave it. Otherwise, split on
    sentence boundaries and force bullets.
    """
    if not summary_text:
        return summary_text

    lines = [l.strip() for l in summary_text.split("\n") if l.strip()]

    # Already bulleted properly
    if len(lines) > 1 and all(l.startswith("-") for l in lines):
        return "\n".join(lines)

    # Fallback: split the blob into sentences and bullet them
    sentences = re.split(r'(?<=[.!?])\s+', summary_text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return "\n".join(f"- {s}" for s in sentences)

def process_attachments(email_item):
    """
    Fast-scans every chunk of every Excel attachment for the student's
    name/regno via plain string match (no LLM call). Only chunks with
    a match get a follow-up LLM call to summarize context.
    """
    findings = []

    for attachment in email_item.get("attachment_chunks", []):
        filename = attachment["filename"]
        chunks = attachment["chunks"]
        total = len(chunks)

        print(f"  Scanning attachment '{filename}' ({total} chunk(s)) for student match...")

        for i, chunk_text in enumerate(chunks):
            matched_term = chunk_contains_student(chunk_text)
            if not matched_term:
                continue

            print(f"    -> Match found in chunk {i + 1}/{total} (matched: '{matched_term}')")
            context = summarize_excel_match(email_item, filename, chunk_text, matched_term, i, total)
            findings.append({
                "filename": filename,
                "chunk_index": i,
                "matched_term": matched_term,
                "context": context,
            })

    if not findings:
        return ""

    return "\n".join(
        f"[{f['filename']}] Found '{f['matched_term']}' — {f['context']}"
        for f in findings
    )

def classify_email(email_item):
    """Sends a single email to LM Studio and parses JSON response"""

    system_prompt = """
You are an AI assistant that analyzes university and professional emails.

Your task is to extract structured information from ONE email.

Return ONLY a valid JSON object with these EXACT keys:

{
  "type": "",
  "title": "",
  "date": "",
  "time": "",
  "priority": "",
  "location": "",
  "sender": "",
  "summary": ""
}

Rules:

- Return ONLY JSON. No markdown. No explanations.
- The "summary" MUST be a bulleted list, never a paragraph.
- Format: each point starts with "- " and is a single, tight sentence — no labels like "What:" or "Action:", just the fact itself.
- 2-4 points max. Merge related info (e.g. a deadline and its consequence) into ONE point instead of two.
- Order: what it is → what's at stake / deadline → what to do, when, where.
- If attachment findings confirm the student's name/regno appears, state that as its own short point (e.g. "Your regno 24BBB1234 is on the shortlist.") - don't just say "the student is included."
- Do not restate the same fact twice across different points.
- If a field is unavailable, return null.
- Preserve dates, times and locations exactly as mentioned.
- Do not invent information.

Type should by any one of these:
Assignment
Exam
Internship
Internship Test
Hackathon
Research
Workshop
Talk
Placement
Holiday
Schedule Change
Birthday
Security Alert
Announcement
Other

Priority Guidelines:

HIGH:
- Internship opportunities
- Internship tests
- Placement activities
- Hackathons
- Assignments
- Exams
- Fee payment deadlines
- Registration deadlines
- Scholarship opportunities

MEDIUM:
- Technical talks
- Workshops
- Research opportunities
- Exchange programs
- Club events the student may be interested in

LOW:
- General announcements
- Celebrations
- Congratulations
- Newsletters
- Promotional emails

The "summary" should cover these as separate bullet points (skip any that don't apply):
- What: what this is, in one line
- Why it matters: the concrete stake for the student (deadline, opportunity, risk)
- Action: what the student should do, and by when, if anything
- If attachment findings mention the student by name/regno, include that as its own point

"""

    attachment_summary = process_attachments(email_item)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Email Details:\nFrom: {email_item['sender']}\n"
                f"Subject: {email_item['subject']}\n"
                f"Body: {email_item['body_preview']}\n"
                f"Attachments: {', '.join(email_item.get('attachment_names', [])) or 'None'}\n"
                f"Relevant findings from attachments:\n{attachment_summary or 'None found'}\n\n"
                "Please extract the information into JSON format. If attachment findings "
                "mention the student by name/regno (e.g. a shortlist), reflect that clearly "
                "in the summary and set priority to HIGH."
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
        "max_tokens": 2500,
    }

    print(f"Processing: {email_item['subject']}...")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=180)

        if response.status_code != 200:
            print(f"  Error from server ({response.status_code}): {response.text[:200]}")
            return None

        response_json = response.json()

        choices = response_json.get("choices")
        if not choices:
            print("  ERROR: No 'choices' in LM Studio response.")
            return None

        llm_response_text = choices[0]["message"]["content"]

        clean_json_str = re.sub(r'^```json\s*', '', llm_response_text, flags=re.MULTILINE)
        clean_json_str = re.sub(r'\s*```$', '', clean_json_str, flags=re.MULTILINE).strip()

        parsed_data = json.loads(clean_json_str)
        # parsed_data["summary"] = normalize_summary(parsed_data.get("summary") or "")

        return {
            "gmail_id": int(email_item["id"]),
            "type": parsed_data.get("type"),
            "title": parsed_data.get("title"),
            "date": parsed_data.get("date"),
            "time": parsed_data.get("time"),
            "priority": parsed_data.get("priority"),
            "location": parsed_data.get("location"),
            "sender": email_item["sender"],
            "summary": parsed_data.get("summary") or "",
            "raw_subject": email_item["subject"],
            "raw_body": email_item["body_preview"],
            "processed_at": firestore.SERVER_TIMESTAMP,
            "model": LM_MODEL_NAME,
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

def get_from_firebase(count):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIAL_PATH)
            initialize_app(cred)

        db = firestore.client()

        docs = (
            db.collection("emails")
            .order_by("gmail_id", direction=firestore.Query.DESCENDING)
            .limit(count)
            .stream()
        )

        return [doc.to_dict() for doc in docs]

    except Exception as e:
        print(f"Firebase error: {e}")
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
            doc_id = item["gmail_id"]

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

def chunk_contains_student(chunk_text):
    """
    Fast, deterministic check: does this chunk of text contain the
    student's name or reg no.? Case-insensitive substring match.
    Returns the matched term, or None.
    """
    chunk_lower = chunk_text.lower()

    for regno in STUDENT_REGNOS:
        if regno.lower() in chunk_lower:
            return regno

    for name in STUDENT_NAMES:
        if name.lower() in chunk_lower:
            return name

    return None

def update_state(state):
    timestamp = firestore.SERVER_TIMESTAMP
    
    item = {
        "state": state,
        "timestamp": timestamp
    }
    
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIAL_PATH)
            initialize_app(cred)

        db = firestore.client()
        doc_id = datetime.now().isoformat()
        try:
            db.collection("heart_beat").document(doc_id).set(item)
        except Exception as e:
            print(f"  Failed to save doc {doc_id}: {e}")
    
    except Exception as e:
        print(f"\nCRITICAL ERROR connecting to Firebase: {e}")
    

def main():    
    update_state("fetching")
    emails = get_emails_from_last_24h(EMAIL_USER, EMAIL_PASS)
    if not emails:
        print("No new emails found.")
        update_state("exit")
        sys.exit(1)

    existing_ids = [email["gmail_id"] for email in get_from_firebase(len(emails))]    
    final_output_list = []
    errors_count = 0

    for i, email_item in enumerate(emails):
        print(f"\n[{i + 1}/{len(emails)}] Analyzing: {email_item['subject']}")

        if(email_item["id"] in existing_ids):
            print("Email already stored")
            continue
        
        result = classify_email(email_item) 

        if result:
            final_output_list.append(result)
            print(f"  -> Extracted Type: {result.get('type', 'Unknown')}, "
                  f"Priority: {result.get('priority', 'N/A')}")
        else:
            errors_count += 1

    # # Output to console (optional, for debugging)
    # if final_output_list:
    #     print("\n" + "=" * 50)
    #     print(f"FINAL OUTPUT ({len(final_output_list)} items):")
    #     print("=" * 50)
    #     with open("extracted_emails_debug.json", "w") as f:
    #         json.dump(final_output_list, f, indent=2)
    #     print("Debug dump saved to 'extracted_emails_debug.json'")

    if errors_count:
        print(f"\n{errors_count} email(s) failed to process.")

    # Save to Firebase
    save_to_firebase(final_output_list)
    update_state("updated")


if __name__ == "__main__":
    main()