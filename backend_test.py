#!/usr/bin/env python3
"""
Silent Honor Foundation Backend API Testing
Tests all backend endpoints for functionality and integration
"""

import requests
import sys
import json
from datetime import datetime
import time

class SilentHonorAPITester:
    def __init__(self, base_url="https://8266e3a7-e97b-4607-8679-48d4f8bffdfd.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_token = None
        self.member_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.test_results = []

    def log_result(self, test_name, success, details="", response_data=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            print(f"❌ {test_name} - {details}")
            self.failed_tests.append(f"{test_name}: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, cookies=None):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers, cookies=cookies)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers, cookies=cookies)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers, cookies=cookies)
            else:
                self.log_result(name, False, f"Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text[:200]}

            if success:
                self.log_result(name, True, f"Status: {response.status_code}", response_data)
            else:
                self.log_result(name, False, f"Expected {expected_status}, got {response.status_code}", response_data)

            return success, response_data

        except Exception as e:
            self.log_result(name, False, f"Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        print("\n🔍 Testing Health Check...")
        success, response = self.run_test(
            "Health Check",
            "GET",
            "/api/health",
            200
        )
        return success

    def test_admin_login(self):
        """Test admin login"""
        print("\n🔍 Testing Admin Login...")
        
        # Use session to maintain cookies
        login_response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": "admin@silenthonor.org", "password": "SilentHonor2024!"}
        )
        
        success = login_response.status_code == 200
        response_data = {}
        try:
            response_data = login_response.json()
        except:
            response_data = {"raw_response": login_response.text[:200]}
        
        if success:
            self.log_result("Admin Login", True, f"Status: {login_response.status_code}", response_data)
            if 'id' in response_data:
                self.admin_token = response_data.get('id')
            return True
        else:
            self.log_result("Admin Login", False, f"Expected 200, got {login_response.status_code}", response_data)
            return False

    def test_admin_me(self):
        """Test admin /me endpoint"""
        print("\n🔍 Testing Admin /me endpoint...")
        
        # Use session with cookies from login
        me_response = self.session.get(f"{self.base_url}/api/auth/me")
        
        success = me_response.status_code == 200
        response_data = {}
        try:
            response_data = me_response.json()
        except:
            response_data = {"raw_response": me_response.text[:200]}
        
        if success:
            is_admin = response_data.get('role') == 'admin'
            self.log_result("Admin Me", is_admin, f"Role: {response_data.get('role', 'unknown')}", response_data)
            return is_admin
        else:
            self.log_result("Admin Me", False, f"Expected 200, got {me_response.status_code}", response_data)
            return False

    def test_member_registration(self):
        """Test member registration"""
        print("\n🔍 Testing Member Registration...")
        test_email = f"test_member_{int(time.time())}@test.com"
        
        # Use a separate session for member registration to avoid interfering with admin session
        member_session = requests.Session()
        
        reg_response = member_session.post(
            f"{self.base_url}/api/auth/register",
            json={
                "email": test_email,
                "password": "TestPass123!",
                "first_name": "Test",
                "last_name": "Member",
                "phone": "555-0123",
                "state": "Missouri",
                "branch": "Army",
                "service_status": "Veteran",
                "years_of_service": "4-8 years",
                "separation_year": "2020",
                "challenges": ["Low or damaged credit score"],
                "notes": "Test member registration"
            }
        )
        
        success = reg_response.status_code == 200
        response_data = {}
        try:
            response_data = reg_response.json()
        except:
            response_data = {"raw_response": reg_response.text[:200]}
        
        if success:
            self.log_result("Member Registration", True, f"Status: {reg_response.status_code}", response_data)
            if 'id' in response_data:
                self.member_token = response_data.get('id')
            return True
        else:
            self.log_result("Member Registration", False, f"Expected 200, got {reg_response.status_code}", response_data)
            return False

    def test_member_login(self):
        """Test member login with newly created account"""
        print("\n🔍 Testing Member Login...")
        # Create a new session for member login
        member_session = requests.Session()
        
        test_email = f"test_login_{int(time.time())}@test.com"
        
        # First register a member
        reg_response = member_session.post(
            f"{self.base_url}/api/auth/register",
            json={
                "email": test_email,
                "password": "TestPass123!",
                "first_name": "Login",
                "last_name": "Test",
                "branch": "Navy",
                "service_status": "Veteran"
            }
        )
        
        if reg_response.status_code != 200:
            self.log_result("Member Login (Registration)", False, f"Registration failed: {reg_response.status_code}")
            return False
        
        # Now test login
        login_response = member_session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": test_email, "password": "TestPass123!"}
        )
        
        success = login_response.status_code == 200
        response_data = {}
        try:
            response_data = login_response.json()
        except:
            response_data = {"raw_response": login_response.text[:200]}
        
        self.log_result("Member Login", success, f"Status: {login_response.status_code}", response_data)
        return success

    def test_contact_form(self):
        """Test contact form submission"""
        print("\n🔍 Testing Contact Form...")
        
        # Use a separate session for contact form to avoid interfering with admin session
        contact_session = requests.Session()
        
        contact_response = contact_session.post(
            f"{self.base_url}/api/contact",
            json={
                "first_name": "Test",
                "last_name": "Contact",
                "email": "test@example.com",
                "branch": "Army",
                "status": "Veteran",
                "topic": "Credit Review & Education",
                "message": "This is a test contact form submission."
            }
        )
        
        success = contact_response.status_code == 200
        response_data = {}
        try:
            response_data = contact_response.json()
        except:
            response_data = {"raw_response": contact_response.text[:200]}
        
        self.log_result("Contact Form", success, f"Status: {contact_response.status_code}", response_data)
        return success

    def test_admin_stats(self):
        """Test admin stats endpoint"""
        print("\n🔍 Testing Admin Stats...")
        
        # Use session with cookies from admin login
        stats_response = self.session.get(f"{self.base_url}/api/admin/stats")
        
        success = stats_response.status_code == 200
        response_data = {}
        try:
            response_data = stats_response.json()
        except:
            response_data = {"raw_response": stats_response.text[:200]}
        
        if success:
            required_fields = ['total_members', 'verified_members', 'pending_verification', 'total_contacts']
            missing_fields = [field for field in required_fields if field not in response_data]
            
            if missing_fields:
                self.log_result("Admin Stats", False, f"Missing fields: {missing_fields}", response_data)
                return False
            else:
                self.log_result("Admin Stats", True, "All required fields present", response_data)
                return True
        else:
            self.log_result("Admin Stats", False, f"Expected 200, got {stats_response.status_code}", response_data)
            return False

    def test_admin_members(self):
        """Test admin members endpoint"""
        print("\n🔍 Testing Admin Members...")
        
        # Use session with cookies from admin login
        members_response = self.session.get(f"{self.base_url}/api/admin/members")
        
        success = members_response.status_code == 200
        response_data = {}
        try:
            response_data = members_response.json()
        except:
            response_data = {"raw_response": members_response.text[:200]}
        
        if success:
            if isinstance(response_data, list):
                self.log_result("Admin Members", True, f"Returned {len(response_data)} members", {"count": len(response_data)})
                return True
            else:
                self.log_result("Admin Members", False, "Response is not a list", response_data)
                return False
        else:
            self.log_result("Admin Members", False, f"Expected 200, got {members_response.status_code}", response_data)
            return False

    def test_admin_contacts(self):
        """Test admin contacts endpoint"""
        print("\n🔍 Testing Admin Contacts...")
        
        # Use session with cookies from admin login
        contacts_response = self.session.get(f"{self.base_url}/api/admin/contacts")
        
        success = contacts_response.status_code == 200
        response_data = {}
        try:
            response_data = contacts_response.json()
        except:
            response_data = {"raw_response": contacts_response.text[:200]}
        
        if success:
            if isinstance(response_data, list):
                self.log_result("Admin Contacts", True, f"Returned {len(response_data)} contacts", {"count": len(response_data)})
                return True
            else:
                self.log_result("Admin Contacts", False, "Response is not a list", response_data)
                return False
        else:
            self.log_result("Admin Contacts", False, f"Expected 200, got {contacts_response.status_code}", response_data)
            return False

    def test_logout(self):
        """Test logout endpoint"""
        print("\n🔍 Testing Logout...")
        
        # Use session with cookies
        logout_response = self.session.post(f"{self.base_url}/api/auth/logout")
        
        success = logout_response.status_code == 200
        response_data = {}
        try:
            response_data = logout_response.json()
        except:
            response_data = {"raw_response": logout_response.text[:200]}
        
        self.log_result("Logout", success, f"Status: {logout_response.status_code}", response_data)
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Silent Honor Foundation Backend API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)

        # Core functionality tests
        tests = [
            self.test_health_check,
            self.test_admin_login,
            self.test_admin_me,
            self.test_member_registration,
            self.test_member_login,
            self.test_contact_form,
            self.test_admin_stats,
            self.test_admin_members,
            self.test_admin_contacts,
            self.test_logout
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_result(test.__name__, False, f"Exception: {str(e)}")

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"   • {failure}")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = SilentHonorAPITester()
    
    try:
        success = tester.run_all_tests()
        
        # Save detailed results
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": tester.tests_run,
            "passed_tests": tester.tests_passed,
            "success_rate": (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0,
            "failed_tests": tester.failed_tests,
            "detailed_results": tester.test_results
        }
        
        with open('/app/test_reports/backend_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"💥 Test execution failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())