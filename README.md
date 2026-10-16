# Email Processing System with REST API

Automated email classification and priority detection system powered by LLM, designed for AWS t3.micro instances. Processes university/professional emails and exposes data via REST API for Android app integration.

## Overview

This system:
- 📧 Fetches emails from Gmail every 15 minutes
- 🤖 Classifies emails using Ollama (qwen3.5:0.8b model)
- 🎯 Assigns priority levels (EXTRA_HIGH, HIGH, LOW)
- 📊 Stores metadata in lightweight SQLite database
- 🌐 Exposes REST API for Android app access
- ⚡ Optimized for AWS t3.micro (1GB RAM, 2 vCPU credits)

## Architecture

```
┌─────────────────────────────────────────┐
│         AWS t3.micro Instance           │
│                                         │
│  ┌────────────┐      ┌──────────┐      │
│  │   Ollama   │◄─────┤  Email   │      │
│  │ qwen3.5:0.8b│      │Processor │      │
│  └────────────┘      └─────┬────┘      │
│                            │            │
│                            ▼            │
│                      ┌──────────┐       │
│                      │  SQLite  │       │
│                      │ Database │       │
│                      └─────┬────┘       │
│                            │            │
│                            ▼            │
│                      ┌──────────┐       │
│                      │ Flask API│       │
│                      │ Port 5000│       │
│                      └─────┬────┘       │
└────────────────────────────┼────────────┘
                             │
                             ▼ HTTPS
                      ┌──────────┐
                      │ Android  │
                      │   App    │
                      └──────────┘
```

## Features

### Email Classification
- **11 Categories**: internship, placement, hackathon, assignment, exam, fee_payment, registration, security_alert, event, other
- **3 Priority Levels**:
  - EXTRA_HIGH: Urgent internships/placements with <2 day deadline
  - HIGH: Important deadlines (assignments, exams, registrations)
  - LOW: General info (events, newsletters)
- **Deadline Extraction**: Automatically extracts dates and times
- **Smart Summaries**: One-line reason for classification

### Database Storage
- **SQLite**: Lightweight, zero-config database
- **Optimized for t3.micro**: WAL mode, indexed queries
- **Deduplication**: Prevents processing same email twice
- **Heartbeat Tracking**: System health monitoring

### REST API
- **7 Endpoints**: Health, emails, sync, stats, heartbeat
- **Incremental Sync**: Only fetch new emails since last check
- **Filtering**: By priority, category, timestamp
- **Fast**: <50ms response time on t3.micro

## Quick Start

### Prerequisites
- AWS t3.micro instance (Ubuntu 22.04 LTS)
- Ollama with qwen3.5:0.8b model
- Gmail account with App Password
- Python 3.8+

### Installation

1. **Clone Repository**
   ```bash
   cd /home/ubuntu
   git clone <your-repo> knowledge-organiser
   cd knowledge-organiser
   ```

2. **Run Deployment Script**
   ```bash
   chmod +x deployment/deploy.sh
   ./deployment/deploy.sh
   ```

3. **Configure Environment**
   Edit `.env` file with your credentials:
   ```env
   EMAIL_USER=your.email@gmail.com
   EMAIL_PASS=your_gmail_app_password
   LM_MODEL_NAME=qwen3.5:0.8b
   STUDENT_NAME=Your Name
   STUDENT_REGNO=21BCE1234
   ```

4. **Verify Installation**
   ```bash
   # Test API
   curl http://localhost:5000/api/health

   # Run email processor manually
   sudo systemctl start email-processor

   # Check logs
   sudo tail -f /var/log/email-api.log
   ```

## Project Structure

```
knowledge-organiser/
├── email_summarizer.py      # Main email processor
├── email_reader.py           # Gmail IMAP client
├── database.py               # SQLite database layer
├── api.py                    # Flask REST API
├── test_database.py          # Database tests
├── test_api.py               # API tests
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
│
├── deployment/
│   ├── deploy.sh             # Automated deployment script
│   ├── email-api.service     # Systemd service for API
│   ├── email-processor.service  # Systemd service for processor
│   └── email-processor.timer    # Systemd timer (15 min interval)
│
├── DATABASE_README.md        # Database documentation
├── API_DOCUMENTATION.md      # API reference
├── DEPLOYMENT_GUIDE.md       # Detailed deployment guide
└── README.md                 # This file
```

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check and system status |
| `/api/emails` | GET | Get emails with filtering |
| `/api/emails/sync` | GET | Incremental sync (recommended) |
| `/api/emails/priority/{level}` | GET | Filter by priority |
| `/api/emails/category/{cat}` | GET | Filter by category |
| `/api/stats` | GET | Database statistics |
| `/api/heartbeat` | GET | System heartbeat logs |

### Example Requests

```bash
# Get recent emails
curl http://your-ip:5000/api/emails?limit=10

# Sync new emails only
curl "http://your-ip:5000/api/emails/sync?last_sync=2024-11-15T10:00:00"

# Get urgent emails
curl http://your-ip:5000/api/emails/priority/EXTRA_HIGH

# Get internship opportunities
curl http://your-ip:5000/api/emails/category/internship

# Database statistics
curl http://your-ip:5000/api/stats
```

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference.

## Android Integration

### Retrofit Setup

```kotlin
interface EmailApiService {
    @GET("api/emails/sync")
    suspend fun syncEmails(
        @Query("last_sync") lastSync: String
    ): SyncResponse
}

val retrofit = Retrofit.Builder()
    .baseUrl("http://your-aws-ip:5000/")
    .addConverterFactory(GsonConverterFactory.create())
    .build()
```

### WorkManager Background Sync

```kotlin
// Run every 15 minutes, WiFi only
val constraints = Constraints.Builder()
    .setRequiredNetworkType(NetworkType.UNMETERED)
    .build()

val syncRequest = PeriodicWorkRequestBuilder<EmailSyncWorker>(
    15, TimeUnit.MINUTES
).setConstraints(constraints).build()

WorkManager.getInstance(context).enqueue(syncRequest)
```

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete Android integration guide.

## Service Management

### Start/Stop Services

```bash
# API service
sudo systemctl start email-api
sudo systemctl stop email-api
sudo systemctl restart email-api

# Email processor
sudo systemctl start email-processor.timer
sudo systemctl stop email-processor.timer
sudo systemctl restart email-processor.timer

# Run processor immediately
sudo systemctl start email-processor
```

### View Logs

```bash
# Live API logs
sudo tail -f /var/log/email-api.log

# Live processor logs
sudo tail -f /var/log/email-processor.log

# Error logs
sudo tail -f /var/log/email-api-error.log
sudo tail -f /var/log/email-processor-error.log

# Systemd journal
sudo journalctl -u email-api -f
sudo journalctl -u email-processor -f
```

### Check Status

```bash
# Service status
sudo systemctl status email-api
sudo systemctl status email-processor.timer

# Database status
sqlite3 emails.db "SELECT COUNT(*) FROM emails;"
sqlite3 emails.db "SELECT priority, COUNT(*) FROM emails GROUP BY priority;"
```

## Testing

### Test Database

```bash
python test_database.py
```

Expected output:
```
✓ Database created successfully
✓ Email saved successfully
✓ Saved 2/2 emails in batch
✓ Retrieved 3 emails
...
✓ All tests passed successfully!
```

### Test API

```bash
# Start API first
python api.py

# In another terminal
python test_api.py
```

Expected output:
```
✓ Health Check - Success
✓ Get Statistics - Success
✓ Get Recent Emails - Success
...
✓ All tests passed! API is working correctly.
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMAIL_USER` | Gmail address | Required |
| `EMAIL_PASS` | Gmail App Password | Required |
| `DB_PATH` | Database file path | `emails.db` |
| `LM_STUDIO_URL` | Ollama API URL | `http://localhost:11434` |
| `LM_MODEL_NAME` | Model to use | `qwen3.5:0.8b` |
| `STUDENT_NAME` | Your full name | Required |
| `STUDENT_REGNO` | Registration number | Required |
| `API_PORT` | API port | `5000` |
| `API_HOST` | API host | `0.0.0.0` |

### Email Categories

The system classifies emails into these categories:

- **internship**: Internship opportunities and tests
- **placement**: Campus placement drives
- **hackathon**: Coding competitions
- **assignment**: Course assignments
- **exam**: Exam schedules (FAT/CAT)
- **fee_payment**: Fee payment notices
- **registration**: Mandatory registrations
- **security_alert**: Account security alerts
- **event**: Workshops, seminars, talks
- **other**: General notices, newsletters

### Priority Rules

1. **EXTRA_HIGH**: `internship` or `placement` with deadline ≤2 days
2. **HIGH**: `assignment`, `exam`, `fee_payment`, `registration`, `hackathon`, or unknown category
3. **LOW**: `event`, `security_alert`, `other`

## Performance

### Resource Usage (t3.micro)

- **Memory**: ~400MB total (Ollama 250MB + Python 150MB)
- **CPU**: Burst to 40% during processing, <5% idle
- **Storage**: ~60KB per 100 emails
- **Network**: Minimal (~5MB/day)

### Response Times

- API endpoints: <50ms average
- Email processing: ~2-3 seconds per email
- Database queries: <10ms

### Optimization Tips

1. **Reduce processor frequency** if CPU credits deplete:
   ```bash
   # Change from 15min to 30min
   sudo nano /etc/systemd/system/email-processor.timer
   # OnUnitActiveSec=30min
   ```

2. **Limit Ollama memory**:
   ```bash
   sudo systemctl edit ollama
   # Add: Environment="OLLAMA_MAX_LOADED_MODELS=1"
   ```

3. **Archive old emails**:
   ```python
   # Delete emails older than 6 months
   db.connection.execute("""
       DELETE FROM emails
       WHERE created_at < datetime('now', '-6 months')
   """)
   ```

## Troubleshooting

### API Won't Start

```bash
# Check logs
sudo journalctl -u email-api -n 50

# Test manually
cd /home/ubuntu/knowledge-organiser
source venv/bin/activate
python api.py
```

### Email Processor Failing

```bash
# Check error logs
sudo tail -50 /var/log/email-processor-error.log

# Common issues:
# - Wrong Gmail credentials (use App Password!)
# - Ollama not running
# - Network issues
```

### Ollama Not Responding

```bash
# Check status
sudo systemctl status ollama

# Restart
sudo systemctl restart ollama

# Verify model
ollama list
```

### Database Locked

```bash
# Stop services
sudo systemctl stop email-api email-processor.timer

# Remove WAL files
rm -f emails.db-shm emails.db-wal

# Restart
sudo systemctl start email-api email-processor.timer
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for more troubleshooting tips.

## Security

Since this is a **personal project**, authentication is omitted for simplicity. For production:

1. **AWS Security Group**: Restrict port 5000 to your IP only
2. **Gmail**: Use App Password, not main password
3. **HTTPS**: Optional - use nginx + Let's Encrypt
4. **API Keys**: Can add simple API key authentication if needed

## Cost Estimate

- **t3.micro**: Free tier (1 year) or ~$7.50/month
- **Storage**: ~$2/month (20GB)
- **Data transfer**: ~$0.50/month
- **Total**: $0-10/month

## Monitoring

### CloudWatch (Optional)

Set up alarms for:
- CPU credit balance < 20%
- Disk usage > 80%
- API response errors

### Local Monitoring

```bash
# Disk space
df -h

# Memory
free -h

# Processes
htop

# Database size
du -h emails.db

# Recent errors
sudo grep -i error /var/log/email-*.log | tail -20
```

## Future Enhancements

- [ ] Push notifications via FCM for EXTRA_HIGH emails
- [ ] Web dashboard for viewing emails
- [ ] Email search functionality
- [ ] Support for multiple email accounts
- [ ] Attachment content analysis
- [ ] Custom category training

## Documentation

- [DATABASE_README.md](DATABASE_README.md) - Database schema and usage
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Complete API reference
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed deployment instructions

## License

Personal project - use as you wish.

## Support

Check logs first:
```bash
sudo tail -f /var/log/email-api.log
sudo tail -f /var/log/email-processor.log
```

Common issues:
1. Wrong Gmail App Password
2. Ollama not running
3. Security group not configured
4. Model not downloaded

---

**Built with**: Python, Flask, SQLite, Ollama, systemd
**Optimized for**: AWS t3.micro, Android integration
**Version**: 1.0
