# Deployment Guide for AWS t3.micro

Complete step-by-step guide to deploy the Email Processing System on AWS.

## Prerequisites

- AWS account with t3.micro instance (Ubuntu 22.04 LTS recommended)
- Ollama installed with qwen3.5:0.8b model
- SSH access to your instance
- Git installed on the instance

## Step 1: Prepare AWS Instance

### Launch t3.micro Instance

1. **EC2 Console** → Launch Instance
2. **AMI**: Ubuntu Server 22.04 LTS
3. **Instance Type**: t3.micro (free tier eligible)
4. **Storage**: 20 GB (default 8GB may be tight with Ollama)
5. **Security Group**: Configure ports
   - SSH (22) - Your IP only
   - Custom TCP (5000) - Your IP only (for API)
   - Optional: HTTP (80) if you plan to use nginx reverse proxy

### Connect to Instance

```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

## Step 2: Install Ollama and Model

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Start Ollama service
sudo systemctl start ollama
sudo systemctl enable ollama

# Pull the model
ollama pull qwen3.5:0.8b

# Verify model is available
ollama list
```

## Step 3: Clone Repository

```bash
cd /home/ubuntu
git clone <your-repo-url> knowledge-organiser
cd knowledge-organiser
```

If you don't have a Git repo yet, you can upload files via SCP:

```bash
# From your local machine
scp -i your-key.pem -r "E:\Knowledge Organiser" ubuntu@your-instance-ip:/home/ubuntu/knowledge-organiser
```

## Step 4: Run Deployment Script

```bash
cd /home/ubuntu/knowledge-organiser
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

The script will:
1. Install system dependencies
2. Create Python virtual environment
3. Install Python packages
4. Set up .env file (you'll need to edit it)
5. Test database functionality
6. Install systemd services
7. Start API and email processor

### Edit Environment Variables

When prompted, edit the `.env` file:

```bash
nano .env
```

Add your credentials:
```env
EMAIL_USER=your.email@gmail.com
EMAIL_PASS=your_app_password
DB_PATH=emails.db
LM_STUDIO_URL=http://localhost:11434
LM_MODEL_NAME=qwen3.5:0.8b
STUDENT_NAME=Your Full Name
STUDENT_REGNO=21BCE1234
API_PORT=5000
API_HOST=0.0.0.0
```

**Important**: Use Gmail App Password, not your regular password:
1. Google Account → Security → 2-Step Verification
2. App Passwords → Generate new
3. Use that 16-character password

## Step 5: Verify Deployment

### Check Services

```bash
# API service
sudo systemctl status email-api

# Email processor timer
sudo systemctl status email-processor.timer

# View recent logs
sudo tail -20 /var/log/email-api.log
```

### Test API Locally

```bash
# Health check
curl http://localhost:5000/api/health

# Get emails
curl http://localhost:5000/api/emails?limit=5

# Get stats
curl http://localhost:5000/api/stats
```

### Test from Your Computer

```bash
# Replace with your instance IP
curl http://your-instance-ip:5000/api/health
```

## Step 6: Run First Email Processing

Manually trigger the email processor to populate the database:

```bash
sudo systemctl start email-processor

# Watch the logs
sudo tail -f /var/log/email-processor.log
```

After successful processing, check the API:

```bash
curl http://localhost:5000/api/emails
```

## Step 7: Configure AWS Security Group

1. **EC2 Console** → Security Groups
2. Find your instance's security group
3. **Inbound Rules** → Edit
4. Add rule:
   - Type: Custom TCP
   - Port: 5000
   - Source: **Your Android device IP** (use whatismyip.com from phone)
   - Or use 0.0.0.0/0 for testing (less secure)

## Step 8: Update Android App

In your Android app, update the base URL:

```kotlin
private const val BASE_URL = "http://your-aws-instance-ip:5000/"

val retrofit = Retrofit.Builder()
    .baseUrl(BASE_URL)
    .addConverterFactory(GsonConverterFactory.create())
    .build()
```

## Service Management Commands

### Start/Stop Services

```bash
# Start API
sudo systemctl start email-api

# Stop API
sudo systemctl stop email-api

# Restart API
sudo systemctl restart email-api

# Start email processor immediately (don't wait for timer)
sudo systemctl start email-processor

# Restart timer
sudo systemctl restart email-processor.timer
```

### View Logs

```bash
# API logs (live)
sudo tail -f /var/log/email-api.log

# Processor logs (live)
sudo tail -f /var/log/email-processor.log

# API errors
sudo tail -f /var/log/email-api-error.log

# Processor errors
sudo tail -f /var/log/email-processor-error.log

# All recent logs
sudo journalctl -u email-api -f
sudo journalctl -u email-processor -f
```

### Service Status

```bash
# Quick status check
sudo systemctl status email-api email-processor.timer

# Check if services are enabled on boot
sudo systemctl is-enabled email-api
sudo systemctl is-enabled email-processor.timer
```

## Database Management

### View Database

```bash
cd /home/ubuntu/knowledge-organiser
sqlite3 emails.db

# Inside sqlite3 shell
.tables
SELECT COUNT(*) FROM emails;
SELECT priority, COUNT(*) FROM emails GROUP BY priority;
.quit
```

### Backup Database

```bash
# Create backup
cp emails.db emails_backup_$(date +%Y%m%d).db

# Or use SQLite backup
sqlite3 emails.db ".backup emails_backup.db"
```

### Reset Database (if needed)

```bash
# Stop services
sudo systemctl stop email-api
sudo systemctl stop email-processor.timer

# Backup and remove
mv emails.db emails.db.old
rm -f emails.db-shm emails.db-wal

# Restart services (database will be recreated)
sudo systemctl start email-api
sudo systemctl start email-processor.timer
```

## Monitoring and Maintenance

### Check Disk Space

```bash
df -h
du -h emails.db
```

### Check Memory Usage

```bash
free -h
htop  # Install with: sudo apt install htop
```

### Update System

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
cd /home/ubuntu/knowledge-organiser
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart email-api
```

## Troubleshooting

### API Not Starting

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
# Check logs
sudo tail -50 /var/log/email-processor-error.log

# Test manually
cd /home/ubuntu/knowledge-organiser
source venv/bin/activate
python email_summarizer.py
```

### Ollama Not Responding

```bash
# Check Ollama status
sudo systemctl status ollama

# Restart Ollama
sudo systemctl restart ollama

# Test Ollama
curl http://localhost:11434/api/tags
```

### Port 5000 Not Accessible

1. Check AWS Security Group allows port 5000
2. Check API is running: `sudo systemctl status email-api`
3. Check from instance: `curl http://localhost:5000/api/health`
4. Check firewall: `sudo ufw status` (should be inactive by default)

### Database Locked

```bash
# Stop services
sudo systemctl stop email-api
sudo systemctl stop email-processor.timer

# Remove lock files
rm -f emails.db-shm emails.db-wal

# Restart
sudo systemctl start email-api
sudo systemctl start email-processor.timer
```

## Optional: Add HTTPS with Nginx

For production, you can add HTTPS:

```bash
# Install nginx
sudo apt install nginx certbot python3-certbot-nginx

# Configure nginx reverse proxy
sudo nano /etc/nginx/sites-available/email-api
```

Add configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/email-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Performance Tuning for t3.micro

The system is already optimized for t3.micro, but here are additional tips:

1. **Monitor CPU credits**: t3.micro uses burst credits
   ```bash
   aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUCreditBalance --dimensions Name=InstanceId,Value=your-instance-id --start-time 2024-11-15T00:00:00Z --end-time 2024-11-15T23:59:59Z --period 3600 --statistics Average
   ```

2. **Reduce email processor frequency** if needed:
   ```bash
   sudo nano /etc/systemd/system/email-processor.timer
   # Change OnUnitActiveSec=15min to 30min
   sudo systemctl daemon-reload
   sudo systemctl restart email-processor.timer
   ```

3. **Limit Ollama memory**:
   ```bash
   sudo systemctl edit ollama
   # Add: [Service]
   # Environment="OLLAMA_MAX_LOADED_MODELS=1"
   sudo systemctl restart ollama
   ```

## Cost Estimate

- **t3.micro**: $0 (free tier) or ~$7.50/month
- **Storage (20 GB)**: ~$2/month
- **Data transfer**: Minimal (~$0.50/month)
- **Total**: ~$0-10/month

## Next Steps

1. ✅ Deploy to AWS
2. ✅ Test API endpoints
3. ✅ Configure Android app
4. Monitor for 24 hours
5. Set up automated backups (optional)
6. Configure CloudWatch alarms (optional)

---

**Need Help?**

Check logs first:
```bash
sudo tail -f /var/log/email-api.log
sudo tail -f /var/log/email-processor.log
```

Most issues are related to:
- Incorrect .env credentials
- Ollama not running
- Security group configuration
- Email app password (not regular password)
