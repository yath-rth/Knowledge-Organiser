#!/bin/bash
# Deployment script for AWS t3.micro instance
# Run this script on your AWS instance after cloning the repository

set -e  # Exit on error

echo "=========================================="
echo "Email Processing System Deployment"
echo "=========================================="
echo ""

# Configuration (project dir = parent of this script, user = whoever runs it)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_DIR="/etc/systemd/system"
RUN_USER="$(whoami)"

echo "Project directory: $PROJECT_DIR"
echo "Service user:      $RUN_USER"
echo ""

echo "Step 1: Installing system dependencies..."
if command -v dnf > /dev/null; then
    # Amazon Linux 2023 / Fedora / RHEL
    sudo dnf install -y python3 python3-pip sqlite
elif command -v yum > /dev/null; then
    # Amazon Linux 2
    sudo yum install -y python3 python3-pip sqlite
elif command -v apt-get > /dev/null; then
    # Ubuntu / Debian
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv sqlite3
else
    echo "Error: No supported package manager found (dnf, yum, apt-get)"
    exit 1
fi

if ! command -v ollama > /dev/null; then
    echo "Warning: ollama not found. Install it before the processor runs:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
fi

echo ""
echo "Step 2: Creating virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate

echo ""
echo "Step 3: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 4: Setting up environment variables..."
if [ ! -f .env ]; then
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Email Configuration
EMAIL_USER=your.email@example.com
EMAIL_PASS=your_app_password
IMAP_SERVER=imap.gmail.com

# Database
DB_PATH=emails.db

# LLM Configuration
LM_STUDIO_URL=http://localhost:11434
LM_MODEL_NAME=qwen3.5:0.8b

# Student Information
STUDENT_NAME=Your Name
STUDENT_REGNO=Your Registration Number

# API Configuration
API_PORT=5000
API_HOST=0.0.0.0
EOF
    echo "Please edit .env file with your credentials:"
    echo "  nano .env"
    echo ""
    read -p "Press Enter after editing .env file..."
fi

echo ""
echo "Step 5: Testing database setup..."
python test_database.py
if [ $? -eq 0 ]; then
    echo "✓ Database test passed"
    rm -f test_emails.db test_emails.db-shm test_emails.db-wal
else
    echo "✗ Database test failed"
    exit 1
fi

echo ""
echo "Step 6: Installing systemd services..."
sudo cp deployment/email-api.service "$SERVICE_DIR/"
sudo cp deployment/email-processor.service "$SERVICE_DIR/"
sudo cp deployment/email-processor.timer "$SERVICE_DIR/"

# Point service files at the actual project dir and user
for svc in email-api.service email-processor.service; do
    sudo sed -i -e "s|/home/ubuntu/knowledge-organiser|$PROJECT_DIR|g" \
                -e "s|^User=ubuntu$|User=$RUN_USER|" "$SERVICE_DIR/$svc"
done

echo ""
echo "Step 7: Creating log files..."
sudo touch /var/log/email-api.log
sudo touch /var/log/email-api-error.log
sudo touch /var/log/email-processor.log
sudo touch /var/log/email-processor-error.log
sudo chown "$RUN_USER:$RUN_USER" /var/log/email-*.log

echo ""
echo "Step 8: Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable email-api.service
sudo systemctl enable email-processor.timer
sudo systemctl start email-api.service
sudo systemctl start email-processor.timer

echo ""
echo "Step 9: Verifying services..."
sleep 2
if sudo systemctl is-active --quiet email-api.service; then
    echo "✓ API service is running"
else
    echo "✗ API service failed to start"
    sudo systemctl status email-api.service
fi

if sudo systemctl is-active --quiet email-processor.timer; then
    echo "✓ Email processor timer is active"
else
    echo "✗ Email processor timer failed to start"
    sudo systemctl status email-processor.timer
fi

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services Status:"
echo "  API:       sudo systemctl status email-api"
echo "  Processor: sudo systemctl status email-processor.timer"
echo ""
echo "View Logs:"
echo "  API:       sudo tail -f /var/log/email-api.log"
echo "  Processor: sudo tail -f /var/log/email-processor.log"
echo ""
echo "API Endpoints:"
echo "  http://$(curl -s ifconfig.me):5000/api/health"
echo "  http://$(curl -s ifconfig.me):5000/api/emails"
echo "  http://$(curl -s ifconfig.me):5000/api/stats"
echo ""
echo "Next Steps:"
echo "1. Test API: curl http://localhost:5000/api/health"
echo "2. Configure AWS Security Group to allow port 5000"
echo "3. Update your Android app with the API URL"
echo "4. Monitor logs for any issues"
echo ""
echo "Troubleshooting:"
echo "  Restart API:       sudo systemctl restart email-api"
echo "  Restart Timer:     sudo systemctl restart email-processor.timer"
echo "  Run processor now: sudo systemctl start email-processor"
echo ""
