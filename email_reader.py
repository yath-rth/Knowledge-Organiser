import imaplib
import os
import sys
import pandas as pd
import email
from datetime import datetime, timedelta
from email.header import decode_header

def is_excel_file(filename):
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in (".xlsx", ".xls", ".xlsm")


def parse_excel_attachment(payload_bytes, filename, rows_per_chunk=200):
    """
    Reads an Excel attachment and returns a list of text chunks,
    each containing up to `rows_per_chunk` rows, so large sheets
    (e.g. 1800-row shortlists) don't get silently truncated.
    """
    import io

    try:
        excel_file = pd.ExcelFile(io.BytesIO(payload_bytes))
        chunks = []

        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            df = df.dropna(how="all").dropna(axis=1, how="all")

            if df.empty:
                continue

            total_rows = len(df)
            for start in range(0, total_rows, rows_per_chunk):
                chunk_df = df.iloc[start:start + rows_per_chunk]
                header = (
                    f"--- Sheet: {sheet_name} "
                    f"(rows {start + 1}-{min(start + rows_per_chunk, total_rows)} of {total_rows}) ---"
                )
                chunks.append(f"{header}\n{chunk_df.to_string(index=False)}")

        if not chunks:
            return [f"(Excel file '{filename}' was empty or unreadable)"]

        return chunks

    except Exception as e:
        return [f"(Error parsing Excel file '{filename}': {e})"]

def load_env():
    try:
        # Check if python-dotenv is installed
        import dotenv
        dotenv.load_dotenv()
        
        EMAIL_USER = os.getenv("EMAIL_USER")
        EMAIL_PASS = os.getenv("EMAIL_PASS")
        IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
        PORT = int(os.getenv("PORT", 993))

        if not EMAIL_USER or not EMAIL_PASS:
            print("Error: Please create a .env file with EMAIL_USER and EMAIL_PASS.")
            sys.exit(1)
            
        return EMAIL_USER, EMAIL_PASS, IMAP_SERVER, PORT
    except ImportError:
        # Fallback if python-dotenv is missing (though you should install it)
        print("Warning: 'python-dotenv' not found. Run: py -3.11 -m pip install python-dotenv")
        return None

def get_emails_from_last_24h(email_user, email_pass, server="imap.gmail.com", port=993):
    # Connect to IMAP server (Gmail uses 'imap.gmail.com')
    mail = imaplib.IMAP4_SSL(server, port) 

    try:
        print(f"Logging in as {email_user}...")
        mail.login(email_user, email_pass)
    except imaplib.IMAP4.error as e:
        print(f"Login failed. Ensure you are using an App Password if 2FA is on.")
        return None

    # FIX: Select the Inbox before searching
    try:
        status, box = mail.select('INBOX') 
        if status != "OK":
            print("Failed to select Inbox.")
            return None
    except Exception as e:
        print(f"Error selecting folder: {e}")
        return None

    # Search for emails received in the last 24 hours
    now = datetime.now()
    cutoff_time = (now - timedelta(hours=24)).strftime('%d-%b-%Y')
    
    search_query = f"SINCE {cutoff_time}" 
    
    status, messages = mail.search(None, search_query)

    if status != "OK":
        print("Search failed.")
        return None

    email_ids = messages[0].split()

    if not email_ids:
        print(f"No emails found in the last 24 hours for {email_user}.")
        mail.close()
        mail.logout()
        return [] # Return empty list instead of exiting logic prematurely

    print(f"Found {len(email_ids)} new emails. Collecting data...\n")
    
    emails_data = []

    # Iterate through found emails
    for e_id in email_ids:
        status, msg_data = mail.fetch(e_id, '(RFC822)')
        
        if status != "OK":
            continue
            
        raw_email = msg_data[0][1]
        message = email.message_from_bytes(raw_email)

        subject_raw = message.get('Subject', 'No Subject')
        from_raw = message.get('From', 'Unknown Sender')

        def decode_mail_header(header):
            try:
                parts = decode_header(header)
                decoded_parts = []
                for part, encoding in parts:
                    if isinstance(part, str):
                        # Already a string (decoded)
                        decoded_parts.append(part)
                    else:
                        # Bytes that need decoding
                        if encoding is None:
                            # Fallback to utf-8 if no encoding specified
                            encoding = 'utf-8' 
                        decoded_parts.append(part.decode(encoding))
                return ''.join(decoded_parts).strip()
            except Exception as e:
                print(f"Warning: Could not decode header '{header}' safely. Returning raw.")
                return str(header)

        subject = decode_mail_header(subject_raw)
        sender = decode_mail_header(from_raw)

        # Extract body text to include in the data payload
        body_text = ""
        attachment_chunks = []  # list of {"filename": ..., "chunks": [...]}
        attachment_names = []

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition())

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body_bytes = part.get_payload(decode=True)
                        if isinstance(body_bytes, bytes):
                            body_text = body_bytes.decode('utf-8', errors='ignore')[:2000]
                        else:
                            body_text = str(body_bytes)[:2000]
                    except Exception as e:
                        print(f"Error reading body for {subject}: {e}")
                    continue

                filename = part.get_filename()
                if filename:
                    decoded_filename = decode_mail_header(filename)
                    attachment_names.append(decoded_filename)

                    # if is_excel_file(decoded_filename):
                    #     try:
                    #         payload = part.get_payload(decode=True)
                    #         if payload:
                    #             chunks = parse_excel_attachment(payload, decoded_filename)
                    #             attachment_chunks.append({
                    #                 "filename": decoded_filename,
                    #                 "chunks": chunks,
                    #             })
                    #             print(f"  -> Parsed Excel attachment: {decoded_filename} "
                    #                   f"({len(chunks)} chunk(s))")
                    #     except Exception as e:
                    #         print(f"  Error parsing attachment {decoded_filename}: {e}")
        else:
            content_type = message.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = message.get_payload()
                    if isinstance(payload, bytes):
                        body_text = payload.decode('utf-8', errors='ignore')[:2000]
                    else:
                        body_text = str(payload)[:2000]
                except Exception as e:
                    print(f"Error reading body for {subject}: {e}")

        # Append structured data to the list
        emails_data.append({
            "id": e_id.decode(),
            "sender": sender,
            "subject": subject,
            "body_preview": body_text,
            "attachment_names": attachment_names,
            "attachment_chunks": attachment_chunks,  # list of {filename, chunks}
        })

    print("Data collection complete.")
    
    mail.close()
    mail.logout()
    
    return emails_data # Return the list of dictionaries
    
def main():
    creds = load_env()
    if creds:
        email_user, email_pass, server, port = creds
        data = get_emails_from_last_24h(email_user, email_pass, server, port)
        if data and len(data) > 0:
            print(f"Successfully fetched {len(data)} emails.")
            # Optional: Print a summary for the user to see it worked before sending to LLM
            for i, em in enumerate(data):
                print(f"{i+1}. From: {em['sender']} - Subject: {em['subject']}")
        else:
            print("No emails returned.")

if __name__ == "__main__":
    main()