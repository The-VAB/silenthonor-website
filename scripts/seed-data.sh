#!/bin/bash
# Silent Honor Foundation - Seed Demo Data Script
# Creates admin user and demo content

set -e

echo "=========================================="
echo "Silent Honor Foundation - Seed Data"
echo "=========================================="

cd /var/www/silenthonor/backend

# Run seed script
python3 seed_demo.py

echo ""
echo "=========================================="
echo "Seed data created!"
echo "=========================================="
echo ""
echo "Demo admin login:"
echo "  Email: admin@silenthonor.org"
echo "  Password: Admin123!"
echo ""
echo "Demo member login:"
echo "  Email: demo@veteran.com"
echo "  Password: Demo123!"
echo ""
