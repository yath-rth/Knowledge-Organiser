import os
import sys
import json
import re
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from email_reader import get_emails_from_last_24h

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234").rstrip("/")
STUDENT_NAME = os.getenv("STUDENT_NAME", "")
STUDENT_REGNO = os.getenv("STUDENT_REGNO", "")

OUTPUT_DIR = "comparison_output"
NUM_LATEST_EMAILS = 5

# Default models to compare. You can add as many as you'd like (e.g. 5 models).
# If empty, the script will attempt to auto-discover models from LM Studio.

MODEL_CONFIGS = [
    {"name": "qwen3.5-9b", "temperature": 0.3, "max_tokens": 1500},
    {"name": "nvidia/nemotron-3-nano-4b", "temperature": 0.3, "max_tokens": 1500},
    {"name": "qwen2.5-0.5b", "temperature": 0.3, "max_tokens": 1500},
    {"name": "minicpm5-1b", "temperature": 0.3, "max_tokens": 1500},
]


def chunk_contains_student(chunk_text):
    if not chunk_text:
        return None
    chunk_lower = chunk_text.lower()
    if STUDENT_REGNO and STUDENT_REGNO.lower() in chunk_lower:
        return STUDENT_REGNO
    if STUDENT_NAME and STUDENT_NAME.lower() in chunk_lower:
        return STUDENT_NAME
    return None

def decode_mail_header(header):
    from email.header import decode_header
    try:
        parts = decode_header(header)
        decoded_parts = []
        for part, encoding in parts:
            if isinstance(part, str):
                decoded_parts.append(part)
            else:
                if encoding is None:
                    encoding = 'utf-8'
                decoded_parts.append(part.decode(encoding))
        return ''.join(decoded_parts).strip()
    except Exception as e:
        return str(header)

def summarize_excel_match(email_item, filename, chunk_text, matched_term, chunk_index, total_chunks, model_name):
    system_prompt = """You are looking at a chunk of rows from an Excel attachment. The student's name or registration number was found in this chunk via exact string match. Your job is only to describe what this sheet appears to be about, using the surrounding row/column context.

Return ONLY a valid JSON object:
{
  "context": "short description of what this list/sheet is (e.g. 'Round 2 interview shortlist for Company X')"
}

Do not invent information you cannot see in the data."""

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
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
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
            return "Match found, but context summary failed."

        content = response.json()["choices"][0]["message"]["content"]
        clean = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE).strip()
        parsed = json.loads(clean)
        return parsed.get("context") or "Match found, context unclear."

    except Exception as e:
        return f"Match found, context extraction error: {str(e)}"

def process_attachments(email_item, model_name):
    findings = []
    for attachment in email_item.get("attachment_chunks", []):
        filename = attachment["filename"]
        chunks = attachment["chunks"]
        total = len(chunks)

        for i, chunk_text in enumerate(chunks):
            matched_term = chunk_contains_student(chunk_text)
            if not matched_term:
                continue

            context = summarize_excel_match(email_item, filename, chunk_text, matched_term, i, total, model_name)
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

def classify_email(email_item, model_config):
    system_prompt = """You are an AI assistant that analyzes university and professional emails.

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

- Title should be short and concise based on the contents of the email.
- Return ONLY JSON. No markdown wrapper outside of potential formatting. No explanations.
- The "summary" MUST be a bulleted list, never a paragraph.
- Format: each point starts with "- " and is a single, tight sentence — no labels like "What:" or "Action:", just the fact itself.
- 2-4 points max. Merge related info into ONE point.
- If attachment findings confirm the student's name/regno appears, state that as its own short point (e.g. "Your regno 24BCE0825 is on the shortlist."). Do not mention if you don't find the exact name and registration number.
- If a field is unavailable, return null.
- Preserve dates, times and locations exactly as mentioned.
- Do not invent information.

Type should be any one of these:
Assignment, Exam, Internship, Internship Test, Hackathon, Research, Workshop, Talk, Placement, Holiday, Schedule Change, Birthday, Security Alert, Announcement, Other

Priority Guidelines:
HIGH: Internship, Internship Test, Placement, Hackathons, Assignments, Exams, Fee payment/Registration deadlines.
LOW: Technical talks, Workshops, Research, Exchange programs, Club events, General announcements, Celebrations, Newsletters, Promotional emails.
"""

    model_name = model_config["name"]
    attachment_summary = process_attachments(email_item, model_name)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Email Details:\nFrom: {email_item['sender']}\n"
                f"Subject: {email_item['subject']}\n"
                f"Name: {STUDENT_NAME}\n"
                f"Registration Number: {STUDENT_REGNO}\n"
                f"Body: {email_item['body_preview']}\n"
                f"Attachments: {', '.join(email_item.get('attachment_names', [])) or 'None'}\n"
                f"Relevant findings from attachments:\n{attachment_summary or 'None found'}\n\n"
                "Extract info into JSON format."
            ),
        },
    ]

    start_time = time.time()
    try:
        response = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": messages,
                "temperature": model_config.get("temperature", 0.3),
                "max_tokens": model_config.get("max_tokens", 1000),
            },
            timeout=180
        )
        latency = time.time() - start_time

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "latency_seconds": latency,
                "model": model_name
            }

        text = response.json()["choices"][0]["message"]["content"]
        clean = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE).strip()
        parsed = json.loads(clean)

        return {
            "success": True,
            "gmail_id": email_item["id"],
            "type": parsed.get("type"),
            "title": parsed.get("title"),
            "date": parsed.get("date"),
            "time": parsed.get("time"),
            "priority": parsed.get("priority"),
            "location": parsed.get("location"),
            "sender": email_item["sender"],
            "summary": parsed.get("summary") or "",
            "raw_subject": email_item["subject"],
            "latency_seconds": latency,
            "model": model_name,
            "processed_at": datetime.now().isoformat()
        }

    except Exception as e:
        latency = time.time() - start_time
        return {
            "success": False,
            "error": str(e),
            "latency_seconds": latency,
            "model": model_name
        }

def discover_models():
    try:
        response = requests.get(f"{LM_STUDIO_URL}/v1/models", timeout=10)
        if response.status_code == 200:
            models = [m["id"] for m in response.json().get("data", [])]
            return [{"name": m, "temperature": 0.3, "max_tokens": 1500} for m in models]
    except Exception as e:
        print(f"Warning: Model discovery failed ({e})")
    return []

def main():
    if not EMAIL_USER or not EMAIL_PASS:
        print("Error: EMAIL_USER and EMAIL_PASS environment variables are required.")
        sys.exit(1)

    # Resolve models to compare
    models_to_compare = MODEL_CONFIGS
    if not models_to_compare:
        print("Attempting to auto-discover models from LM Studio...")
        models_to_compare = discover_models()
        if not models_to_compare:
            print("No models defined and auto-discovery failed. Please configure MODEL_CONFIGS.")
            sys.exit(1)

    print(f"Comparing {len(models_to_compare)} models:")
    for m in models_to_compare:
        print(f" - {m['name']}")

    print("\nFetching emails...")
    emails = get_emails_from_last_24h(EMAIL_USER, EMAIL_PASS)
    if not emails:
        print("No emails found.")
        sys.exit(0)

    # Get the latest 5 emails (sorting descending by id)
    emails.sort(key=lambda x: int(x["id"]), reverse=True)
    emails = emails[:NUM_LATEST_EMAILS]
    # Re-sort ascending so they process in chronological order
    emails.sort(key=lambda x: int(x["id"]))

    print(f"Selected the latest {len(emails)} emails for comparison:")
    for em in emails:
        print(f" [{em['id']}] {decode_mail_header(em['subject'])}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    combined_results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_emails_processed": len(emails),
            "models_compared": [m["name"] for m in models_to_compare]
        },
        "emails": [
            {
                "gmail_id": em["id"],
                "subject": decode_mail_header(em["subject"]),
                "sender": decode_mail_header(em["sender"])
            }
            for em in emails
        ],
        "results_by_model": {}
    }

    for config in models_to_compare:
        model_name = config["name"]
        print(f"\nProcessing with model: {model_name}")
        model_results = []

        for em in emails:
            print(f" -> Classifying email [{em['id']}]...")
            result = classify_email(em, config)
            model_results.append(result)

        # Save individual model results
        safe_model_name = re.sub(r'[^A-Za-z0-9._-]', '_', model_name)
        individual_file = os.path.join(OUTPUT_DIR, f"model_{safe_model_name}_results.json")
        with open(individual_file, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "model": model_name,
                    "processed_at": datetime.now().isoformat(),
                    "total_emails": len(emails)
                },
                "results": model_results
            }, f, indent=2)
        print(f"Saved results to {individual_file}")

        combined_results["results_by_model"][model_name] = model_results

    # Save combined results
    combined_file = os.path.join(OUTPUT_DIR, "all_models_comparison.json")
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(combined_results, f, indent=2)
    print(f"\nSaved combined comparison data to {combined_file}")
    print("\nComparison run complete! Run your HTML generator to visualize.")

if __name__ == "__main__":
    main()
