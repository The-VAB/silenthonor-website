#!/bin/bash
# Silent Honor Foundation - Production Deployment Script
# Server: 72.60.175.115
# Usage: ./scripts/deploy.sh

set -e

# Configuration
SERVER="root@72.60.175.115"
APP_DIR="/var/www/silenthonor"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
SERVICE_NAME="silenthonor"

echo "=========================================="
echo "Silent Honor Foundation Deployment"
echo "=========================================="

# Pull latest code
echo ""
echo "[1/5] Pulling latest code from GitHub..."
ssh $SERVER "cd $APP_DIR && git pull origin main"

# Install backend dependencies
echo ""
echo "[2/5] Installing backend dependencies..."
ssh $SERVER "cd $BACKEND_DIR && pip install -r requirements.txt"

# Restart backend service
echo ""
echo "[3/5] Restarting backend service..."
ssh $SERVER "systemctl restart $SERVICE_NAME"

# Wait for service to start
echo ""
echo "[4/5] Waiting for service to start..."
sleep 3

# Check service status
echo ""
echo "[5/5] Checking service status..."
ssh $SERVER "systemctl status $SERVICE_NAME --no-pager"

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "API: https://api.srv1077820.hstgr.cloud"
echo "Frontend: https://silenthonorfoundation.org"
echo ""
