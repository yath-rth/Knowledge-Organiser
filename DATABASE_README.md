# Email Database Documentation

## Overview

The email processing system now uses **SQLite** for local database storage instead of Firebase. This provides:
- **Lightweight operation** - Perfect for t3.micro AWS instances
- **Zero external dependencies** - No cloud services needed
- **Cost-effective** - No Firebase costs
- **Fast local queries** - Ideal for API responses

## Database Schema

### Emails Table
Stores all processed emails with metadata:

| Column | Type | Description |
|--------|------|-------------|
| gmail_id | INTEGER (PK) | Unique Gmail message ID |
| reason | TEXT | Short explanation from LLM |
| priority | TEXT | HIGH, EXTRA_HIGH, or LOW |
| category | TEXT | Email category (internship, placement, etc.) |
| deadline | TEXT | ISO 8601 deadline (if any) |
| sender | TEXT | Email sender address |
| raw_subject | TEXT | Original email subject |
| raw_body | TEXT | Email body preview |
| processed_at | TEXT | ISO 8601 processing timestamp |
| model | TEXT | LLM model used for processing |
| created_at | TEXT | Database insertion timestamp |

**Indexes:**
- `idx_priority_deadline` - For priority-based queries
- `idx_category` - For category filtering
- `idx_processed_at` - For time-based queries

### Heartbeat Table
Tracks system state for monitoring:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PK) | Auto-increment ID |
| state | TEXT | System state description |
| timestamp | TEXT | ISO 8601 timestamp |
| created_at | TEXT | Database insertion timestamp |

**Indexes:**
- `idx_heartbeat_timestamp` - For time-based queries

## Usage

### Basic Operations

```python
from database import EmailDatabase

# Initialize database
db = EmailDatabase("emails.db")

# Save a single email
email_data = {
    "gmail_id": 12345,
    "reason": "Assignment deadline approaching",
    "priority": "HIGH",
    "category": "assignment",
    "deadline": "2024-12-31T23:59:00",
    "sender": "professor@university.edu",
    "raw_subject": "CS101 Assignment Due",
    "raw_body": "Submit by end of month...",
    "processed_at": datetime.now().isoformat(),
    "model": "qwen3.5:0.8b"
}
db.save_email(email_data)

# Save multiple emails (better performance)
db.save_emails_batch([email1, email2, email3])

# Retrieve recent emails
recent = db.get_recent_emails(limit=50)

# Filter by priority
high_priority = db.get_emails_by_priority("HIGH", limit=20)

# Filter by category
internships = db.get_emails_by_category("internship")

# Check if email exists (deduplication)
exists = db.email_exists(12345)

# Get existing IDs for bulk deduplication
existing_ids = db.get_existing_email_ids(limit=100)

# Update heartbeat
db.update_heartbeat("processing_complete")

# Get statistics
stats = db.get_statistics()
print(f"Total emails: {stats['total_emails']}")
print(f"By priority: {stats['priority_breakdown']}")
```

### Environment Variables

Add to your `.env` file:

```bash
# Database path (optional, defaults to emails.db)
DB_PATH=emails.db

# Email credentials
EMAIL_USER=your.email@example.com
EMAIL_PASS=your_app_password

# LLM configuration
LM_STUDIO_URL=http://localhost:11434
LM_MODEL_NAME=qwen3.5:0.8b

# Student info (for attachment scanning)
STUDENT_NAME=Your Name
STUDENT_REGNO=Your Registration Number
```

## Running the System

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test Database
```bash
python test_database.py
```

### 3. Run Email Processor
```bash
python email_summarizer.py
```

The database file `emails.db` will be created automatically on first run.

## API Integration (Next Steps)

The database is ready for API integration. You can now:

1. Create a REST API using Flask/FastAPI
2. Expose endpoints for:
   - GET `/emails` - List recent emails
   - GET `/emails/priority/{priority}` - Filter by priority
   - GET `/emails/category/{category}` - Filter by category
   - GET `/stats` - Database statistics
   - GET `/heartbeat` - System health check

Example API structure:
```python
from flask import Flask, jsonify
from database import EmailDatabase

app = Flask(__name__)
db = EmailDatabase()

@app.route('/api/emails')
def get_emails():
    emails = db.get_recent_emails(limit=50)
    return jsonify(emails)

@app.route('/api/emails/priority/<priority>')
def get_by_priority(priority):
    emails = db.get_emails_by_priority(priority, limit=50)
    return jsonify(emails)
```

## Performance Optimization

For t3.micro instances:
- Database uses WAL mode for better concurrency
- PRAGMA synchronous=NORMAL for balanced performance
- Batch operations for bulk inserts
- Indexes on commonly queried columns
- Typical database size: ~30KB per 100 emails

## Migration from Firebase

The system has been migrated from Firebase to SQLite:
- ✅ Removed firebase-admin dependency
- ✅ All Firebase operations replaced with SQLite equivalents
- ✅ Heartbeat tracking maintained
- ✅ Same data structure preserved
- ✅ Better performance on t3.micro

## Database Backup

To backup your database:
```bash
# Simple file copy
cp emails.db emails_backup_$(date +%Y%m%d).db

# Or use SQLite backup command
sqlite3 emails.db ".backup emails_backup.db"
```

## Troubleshooting

**Issue: Database locked**
- Solution: Ensure only one process writes at a time, or use context managers

**Issue: Performance degradation**
- Solution: Run `VACUUM` periodically to optimize
  ```bash
  sqlite3 emails.db "VACUUM;"
  ```

**Issue: Disk space on t3.micro**
- Solution: Archive old emails or set up periodic cleanup
  ```python
  # Delete emails older than 6 months
  db.connection.execute("""
      DELETE FROM emails
      WHERE created_at < datetime('now', '-6 months')
  """)
  db.connection.commit()
  ```
