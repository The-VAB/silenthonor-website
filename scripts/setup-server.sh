#!/bin/bash
# Silent Honor Foundation - Server Setup Script
# Run this once on a fresh server to set up the environment
# Server: 72.60.175.115

set -e

echo "=========================================="
echo "Silent Honor Foundation Server Setup"
echo "=========================================="

# Update system
echo ""
echo "[1/8] Updating system packages..."
apt-get update && apt-get upgrade -y

# Install dependencies
echo ""
echo "[2/8] Installing system dependencies..."
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    curl

# Create application directory
echo ""
echo "[3/8] Creating application directory..."
mkdir -p /var/www/silenthonor
cd /var/www/silenthonor

# Clone repository (if not exists)
echo ""
echo "[4/8] Cloning repository..."
if [ ! -d ".git" ]; then
    git clone https://github.com/mlugenbell/silenthonor-website.git .
else
    git pull origin main
fi

# Install Python dependencies
echo ""
echo "[5/8] Installing Python dependencies..."
cd /var/www/silenthonor/backend
pip3 install -r requirements.txt

# Create uploads directory
echo ""
echo "[6/8] Creating uploads directory..."
mkdir -p /var/www/silenthonor/backend/uploads/dd214
chmod 755 /var/www/silenthonor/backend/uploads

# Create systemd service
echo ""
echo "[7/8] Creating systemd service..."
cat > /etc/systemd/system/silenthonor.service << 'EOF'
[Unit]
Description=Silent Honor Foundation API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/silenthonor/backend
Environment="PATH=/usr/local/bin:/usr/bin"
EnvironmentFile=/var/www/silenthonor/backend/.env
ExecStart=/usr/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable silenthonor
systemctl start silenthonor

# Configure Nginx
echo ""
echo "[8/8] Configuring Nginx..."
cat > /etc/nginx/sites-available/silenthonor-api << 'EOF'
server {
    listen 80;
    server_name api.srv1077820.hstgr.cloud;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Increase timeout for uploads
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        client_max_body_size 20M;
    }
}
EOF

ln -sf /etc/nginx/sites-available/silenthonor-api /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo ""
echo "=========================================="
echo "Server setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Create /var/www/silenthonor/backend/.env with your configuration"
echo "2. Run: certbot --nginx -d api.srv1077820.hstgr.cloud"
echo "3. Restart the service: systemctl restart silenthonor"
echo ""
