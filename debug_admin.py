#!/usr/bin/env python3
"""
Debug admin authentication issue
"""

import requests
import json

def debug_admin_auth():
    base_url = "https://8266e3a7-e97b-4607-8679-48d4f8bffdfd.preview.emergentagent.com"
    session = requests.Session()
    
    print("🔍 Debugging Admin Authentication...")
    
    # Step 1: Login as admin
    print("\n1. Admin Login...")
    login_response = session.post(
        f"{base_url}/api/auth/login",
        json={"email": "admin@silenthonor.org", "password": "SilentHonor2024!"}
    )
    
    print(f"Login Status: {login_response.status_code}")
    print(f"Login Response: {login_response.text}")
    print(f"Cookies after login: {dict(session.cookies)}")
    
    if login_response.status_code != 200:
        print("❌ Admin login failed!")
        return
    
    # Step 2: Check /me endpoint
    print("\n2. Check /me endpoint...")
    me_response = session.get(f"{base_url}/api/auth/me")
    print(f"Me Status: {me_response.status_code}")
    print(f"Me Response: {me_response.text}")
    
    if me_response.status_code == 200:
        user_data = me_response.json()
        print(f"User Role: {user_data.get('role')}")
        print(f"User ID: {user_data.get('_id')}")
    
    # Step 3: Try admin stats
    print("\n3. Try admin stats...")
    stats_response = session.get(f"{base_url}/api/admin/stats")
    print(f"Stats Status: {stats_response.status_code}")
    print(f"Stats Response: {stats_response.text}")
    
    # Step 4: Check headers
    print(f"\n4. Request headers for stats:")
    print(f"Cookies: {dict(session.cookies)}")

if __name__ == "__main__":
    debug_admin_auth()