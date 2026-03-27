#!/usr/bin/env python3
"""
Backend API Testing for Identity & Employee Hub
Tests all CRUD operations, authentication, and integrations
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class IdentityHubAPITester:
    def __init__(self, base_url: str = "https://employee-hub-283.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.created_resources = {
            'apps': [],
            'users': [],
            'roles': [],
            'employees': []
        }

    def log(self, message: str, level: str = "INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", "PASS")
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                if response.text:
                    self.log(f"Response: {response.text[:200]}", "ERROR")

            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {}

            return success, response_data

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}", "ERROR")
            return False, {}

    def test_health_check(self):
        """Test basic health endpoints"""
        self.log("=== HEALTH CHECK TESTS ===")
        self.run_test("API Root", "GET", "", 200)
        self.run_test("Health Check", "GET", "health", 200)

    def test_authentication(self):
        """Test authentication flows"""
        self.log("=== AUTHENTICATION TESTS ===")
        
        # Test login with admin credentials
        login_data = {
            "email": "steve.harding@me.com",
            "password": "ChangeMeNow!"
        }
        success, response = self.run_test("Admin Login", "POST", "auth/login", 200, login_data)
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log(f"✅ Token acquired for user: {response['user']['email']}")
        else:
            self.log("❌ Failed to get authentication token", "ERROR")
            return False

        # Test token verification
        self.run_test("Token Verification", "GET", "auth/verify", 200)
        
        # Test get current user
        self.run_test("Get Current User", "GET", "auth/me", 200)
        
        # Test magic link request (should work even if email doesn't exist)
        magic_data = {"email": "test@example.com"}
        self.run_test("Magic Link Request", "POST", "auth/magic-link", 200, magic_data)
        
        return True

    def test_apps_crud(self):
        """Test Apps CRUD operations"""
        self.log("=== APPS CRUD TESTS ===")
        
        # List apps
        self.run_test("List Apps", "GET", "apps", 200)
        self.run_test("List Apps (Include Inactive)", "GET", "apps?include_inactive=true", 200)
        
        # Create app
        app_data = {
            "name": "Test App",
            "url": "https://test-app.example.com",
            "icon": "LayoutDashboard",
            "description": "Test application for API testing",
            "is_active": True
        }
        success, response = self.run_test("Create App", "POST", "apps", 200, app_data)
        
        if success and 'id' in response:
            app_id = response['id']
            self.created_resources['apps'].append(app_id)
            
            # Get app by ID
            self.run_test("Get App by ID", "GET", f"apps/{app_id}", 200)
            
            # Update app
            update_data = {
                "name": "Updated Test App",
                "description": "Updated description"
            }
            self.run_test("Update App", "PUT", f"apps/{app_id}", 200, update_data)
            
            return app_id
        
        return None

    def test_users_crud(self):
        """Test Users CRUD operations"""
        self.log("=== USERS CRUD TESTS ===")
        
        # List users
        self.run_test("List Users", "GET", "users", 200)
        
        # Create user
        user_data = {
            "email": "testuser@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "user"
        }
        success, response = self.run_test("Create User", "POST", "users", 200, user_data)
        
        if success and 'id' in response:
            user_id = response['id']
            self.created_resources['users'].append(user_id)
            
            # Get user by ID
            self.run_test("Get User by ID", "GET", f"users/{user_id}", 200)
            
            # Update user
            update_data = {
                "first_name": "Updated Test",
                "last_name": "Updated User"
            }
            self.run_test("Update User", "PUT", f"users/{user_id}", 200, update_data)
            
            return user_id
        
        return None

    def test_roles_crud(self):
        """Test Roles CRUD operations"""
        self.log("=== ROLES CRUD TESTS ===")
        
        # List roles
        self.run_test("List Roles", "GET", "roles", 200)
        
        # Create role
        role_data = {
            "name": "Test Role",
            "description": "Test role for API testing"
        }
        success, response = self.run_test("Create Role", "POST", "roles", 200, role_data)
        
        if success and 'id' in response:
            role_id = response['id']
            self.created_resources['roles'].append(role_id)
            
            # Get role by ID
            self.run_test("Get Role by ID", "GET", f"roles/{role_id}", 200)
            
            # Update role
            update_data = {
                "name": "Updated Test Role",
                "description": "Updated description"
            }
            self.run_test("Update Role", "PUT", f"roles/{role_id}", 200, update_data)
            
            return role_id
        
        return None

    def test_employees_crud(self):
        """Test Employees CRUD operations"""
        self.log("=== EMPLOYEES CRUD TESTS ===")
        
        # List employees
        self.run_test("List Employees", "GET", "employees", 200)
        
        # Test search
        self.run_test("Search Employees", "GET", "employees?search=test", 200)
        
        # Create employee
        employee_data = {
            "first_name": "Test",
            "last_name": "Employee",
            "email": "testemployee@example.com",
            "department": "Engineering",
            "job_title": "Software Engineer",
            "status": "active"
        }
        success, response = self.run_test("Create Employee", "POST", "employees", 200, employee_data)
        
        if success and 'id' in response:
            employee_id = response['id']
            self.created_resources['employees'].append(employee_id)
            
            # Get employee by ID
            self.run_test("Get Employee by ID", "GET", f"employees/{employee_id}", 200)
            
            # Update employee
            update_data = {
                "department": "Product",
                "job_title": "Product Manager"
            }
            self.run_test("Update Employee", "PUT", f"employees/{employee_id}", 200, update_data)
            
            return employee_id
        
        return None

    def test_assignments(self, app_id: str, user_id: str, role_id: str):
        """Test assignment operations"""
        self.log("=== ASSIGNMENT TESTS ===")
        
        if not all([app_id, user_id, role_id]):
            self.log("⚠️ Skipping assignment tests - missing required resources", "WARN")
            return
        
        # Role-App assignment
        self.run_test("Assign App to Role", "POST", f"roles/{role_id}/apps?app_id={app_id}", 200)
        
        # User-Role assignment
        self.run_test("Assign Role to User", "POST", f"users/{user_id}/roles?role_id={role_id}", 200)
        
        # User-App direct assignment
        self.run_test("Assign App to User", "POST", f"users/{user_id}/apps?app_id={app_id}&is_granted=true", 200)
        
        # Test removal
        self.run_test("Remove App from User", "DELETE", f"users/{user_id}/apps/{app_id}", 200)
        self.run_test("Remove Role from User", "DELETE", f"users/{user_id}/roles/{role_id}", 200)
        self.run_test("Remove App from Role", "DELETE", f"roles/{role_id}/apps/{app_id}", 200)

    def test_launchpad(self):
        """Test launchpad endpoint"""
        self.log("=== LAUNCHPAD TESTS ===")
        self.run_test("Get Launchpad", "GET", "launchpad", 200)

    def test_settings(self):
        """Test settings endpoints"""
        self.log("=== SETTINGS TESTS ===")
        
        # Get settings
        self.run_test("Get BambooHR Settings", "GET", "settings/bamboohr", 200)
        self.run_test("Get Azure SSO Settings", "GET", "settings/azure-sso", 200)
        
        # Update BambooHR settings
        bamboo_data = {
            "api_key": "test-key",
            "company_domain": "testcompany",
            "sync_enabled": False
        }
        self.run_test("Update BambooHR Settings", "PUT", "settings/bamboohr", 200, bamboo_data)
        
        # Update Azure settings
        azure_data = {
            "tenant_id": "test-tenant-id",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "enabled": False
        }
        self.run_test("Update Azure SSO Settings", "PUT", "settings/azure-sso", 200, azure_data)
        
        # Test BambooHR sync (should fail without proper credentials)
        self.run_test("Trigger BambooHR Sync", "POST", "settings/bamboohr/sync", 400)

    def cleanup_resources(self):
        """Clean up created test resources"""
        self.log("=== CLEANUP ===")
        
        # Delete in reverse order to handle dependencies
        for employee_id in self.created_resources['employees']:
            self.run_test(f"Delete Employee {employee_id}", "DELETE", f"employees/{employee_id}", 200)
        
        for user_id in self.created_resources['users']:
            self.run_test(f"Delete User {user_id}", "DELETE", f"users/{user_id}", 200)
        
        for role_id in self.created_resources['roles']:
            self.run_test(f"Delete Role {role_id}", "DELETE", f"roles/{role_id}", 200)
        
        for app_id in self.created_resources['apps']:
            self.run_test(f"Delete App {app_id}", "DELETE", f"apps/{app_id}", 200)

    def run_all_tests(self):
        """Run all backend tests"""
        self.log("🚀 Starting Identity & Employee Hub Backend API Tests")
        self.log(f"Base URL: {self.base_url}")
        
        try:
            # Basic health checks
            self.test_health_check()
            
            # Authentication
            if not self.test_authentication():
                self.log("❌ Authentication failed - stopping tests", "ERROR")
                return False
            
            # CRUD operations
            app_id = self.test_apps_crud()
            user_id = self.test_users_crud()
            role_id = self.test_roles_crud()
            employee_id = self.test_employees_crud()
            
            # Assignment operations
            self.test_assignments(app_id, user_id, role_id)
            
            # Launchpad
            self.test_launchpad()
            
            # Settings
            self.test_settings()
            
            # Cleanup
            self.cleanup_resources()
            
            # Final results
            self.log("=" * 50)
            self.log(f"📊 FINAL RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
            success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
            self.log(f"📈 Success Rate: {success_rate:.1f}%")
            
            if success_rate >= 90:
                self.log("🎉 Backend API tests PASSED!", "SUCCESS")
                return True
            else:
                self.log("⚠️ Backend API tests had issues", "WARN")
                return False
                
        except Exception as e:
            self.log(f"💥 Test suite failed with error: {str(e)}", "ERROR")
            return False

def main():
    """Main test runner"""
    tester = IdentityHubAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())