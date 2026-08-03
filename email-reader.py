import imaplib
import os
import sys
import email
from datetime import datetime, timedelta
from email.header import decode_header

# Load environment variables from .env file
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
        return

    # FIX: Select the Inbox before searching
    try:
        status, box = mail.select('INBOX') 
        if status != "OK":
            print("Failed to select Inbox.")
            return
    except Exception as e:
        print(f"Error selecting folder: {e}")
        return

    # Search for emails received in the last 24 hours
    now = datetime.now()
    cutoff_time = (now - timedelta(hours=24)).strftime('%d-%b-%Y')
    
    search_query = f"SINCE {cutoff_time}" 
    
    status, messages = mail.search(None, search_query)

    if status != "OK":
        print("Search failed.")
        return

    email_ids = messages[0].split()

    if not email_ids:
        print(f"No emails found in the last 24 hours for {email_user}.")
        mail.close()
        mail.logout()
        return

    print(f"Found {len(email_ids)} new emails. Processing...\n")

    # Iterate through found emails
    for e_id in email_ids:
        status, msg_data = mail.fetch(e_id, '(RFC822)')
        
        if status != "OK":
            continue
            
        raw_email = msg_data[0][1]
        message = email.message_from_bytes(raw_email)

        subject_raw = message.get('Subject')
        from_raw = message.get('From')

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

        print(f"--- New Email ---")
        print(f"From: {sender}")
        print(f"Subject: {subject}\n")
        
        # Optional: Print body snippet
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition())
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # print(body[:500])  # Uncomment to see first 500 chars of body
                        break
                    except Exception as e:
                        print(f"Error reading body: {e}")
        else:
            content_type = message.get_content_type()
            if content_type == "text/plain":
                try:
                    body = message.get_payload().decode('utf-8', errors='ignore')
                    # print(body[:500])  # Uncomment to see first 500 chars of body
                except Exception as e:
                    print(f"Error reading body: {e}")

    print("Done!")
    
    mail.close()
    mail.logout()

if __name__ == "__main__":
    print("Fetching emails from the last 24 hours...")
    get_emails_from_last_24h(EMAIL_USER, EMAIL_PASS)