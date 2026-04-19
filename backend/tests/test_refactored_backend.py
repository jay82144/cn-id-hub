"""
Test suite for Identity & Employee Hub v3.1.0 - Refactored Backend
Tests the modular route architecture after refactoring from ~1955 to ~1067 lines

Modules tested:
- routes/auth.py - Authentication routes
- routes/admin.py - Audit logs and migrations
- routes/email.py - Email service
- routes/api_keys.py - API key management
- routes/identity.py - Identity context for downstream apps
- server.py - Companies, Users, Apps, Roles, Employees
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin.test@identity.hub"
ADMIN_PASSWORD = "SecureTest123!"


class TestHealthAndRoot:
    """Basic health check tests"""
    
    def test_root_endpoint(self):
        """Test root endpoint returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Identity & Employee Hub API"
        assert data["version"] == "3.1.0"
        print("✓ Root endpoint returns v3.1.0")
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("✓ Health endpoint returns healthy")


class TestAuthRoutes:
    """Test authentication routes from routes/auth.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "sysadmin"
        print("✓ Login returns access_token and user info")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials return 401")
    
    def test_get_current_user(self, auth_token):
        """Test GET /api/auth/me endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print("✓ GET /api/auth/me returns current user")
    
    def test_verify_token(self, auth_token):
        """Test token verification endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("valid") == True
        print("✓ Token verification works")
    
    def test_magic_link_request(self):
        """Test magic link request endpoint"""
        response = requests.post(f"{BASE_URL}/api/auth/magic-link", json={
            "email": ADMIN_EMAIL
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # In dev mode, debug_token is returned
        print("✓ Magic link request works")


class TestAdminRoutes:
    """Test admin routes from routes/admin.py - Audit logs and migrations"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_audit_logs(self, auth_token):
        """Test GET /api/admin/audit-logs endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)
        print(f"✓ Audit logs endpoint returns {data['total']} events")
    
    def test_get_audit_logs_with_filters(self, auth_token):
        """Test audit logs with action filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=create&limit=5",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # All returned logs should have action=create
        for log in data["logs"]:
            assert log["action"] == "create"
        print("✓ Audit logs filtering by action works")
    
    def test_get_audit_actions(self, auth_token):
        """Test GET /api/admin/audit-logs/actions endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs/actions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "resource_types" in data
        assert "create" in data["actions"]
        assert "user" in data["resource_types"]
        print("✓ Audit actions endpoint returns action types")
    
    def test_get_migration_status(self, auth_token):
        """Test GET /api/admin/migrations endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/migrations",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "current_revision" in data or "migrations" in data
        print("✓ Migration status endpoint works")
    
    def test_get_pending_migrations(self, auth_token):
        """Test GET /api/admin/migrations/pending endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/migrations/pending",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_count" in data
        assert "is_up_to_date" in data
        print(f"✓ Pending migrations: {data['pending_count']}, up_to_date: {data['is_up_to_date']}")
    
    def test_get_schema_changelog(self, auth_token):
        """Test GET /api/admin/schema/changelog endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/schema/changelog",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "changelog" in data
        print("✓ Schema changelog endpoint works")
    
    def test_audit_logs_require_sysadmin(self):
        """Test that audit logs require sysadmin role"""
        response = requests.get(f"{BASE_URL}/api/admin/audit-logs")
        assert response.status_code in [401, 403]
        print("✓ Audit logs require authentication")


class TestEmailRoutes:
    """Test email service routes from routes/email.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_email_status(self, auth_token):
        """Test GET /api/email/status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/email/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "provider" in data
        # Should be in mock mode since RESEND_API_KEY is not set
        assert data["provider"] == "mock"
        print(f"✓ Email status: provider={data['provider']}, configured={data['configured']}")
    
    def test_email_templates(self, auth_token):
        """Test GET /api/email/templates endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/email/templates",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert "magic_link" in data["templates"]
        assert "password_reset" in data["templates"]
        print(f"✓ Email templates: {data['templates']}")
    
    def test_send_email_mock(self, auth_token):
        """Test POST /api/email/send endpoint (mock mode)"""
        response = requests.post(
            f"{BASE_URL}/api/email/send",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "to": ["test@example.com"],
                "subject": "Test Email",
                "text": "This is a test email"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["mock"] == True  # Should be in mock mode
        print("✓ Email send works in mock mode")
    
    def test_email_requires_auth(self):
        """Test that email endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/email/status")
        assert response.status_code in [401, 403]
        print("✓ Email endpoints require authentication")


class TestCompaniesRoutes:
    """Test companies CRUD from server.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_list_companies(self, auth_token):
        """Test GET /api/companies endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least Acme Corp and TechStart Inc from seed data
        company_names = [c["name"] for c in data]
        print(f"✓ Companies list: {company_names}")
    
    def test_get_company_branding(self, auth_token):
        """Test GET /api/companies/{id}/branding endpoint (public)"""
        # First get a company ID
        response = requests.get(
            f"{BASE_URL}/api/companies",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        companies = response.json()
        if companies:
            company_id = companies[0]["id"]
            # Branding endpoint is public
            response = requests.get(f"{BASE_URL}/api/companies/{company_id}/branding")
            assert response.status_code == 200
            data = response.json()
            assert "name" in data
            print(f"✓ Company branding for {data['name']}")
    
    def test_companies_require_sysadmin(self):
        """Test that companies list requires sysadmin"""
        response = requests.get(f"{BASE_URL}/api/companies")
        assert response.status_code in [401, 403]
        print("✓ Companies endpoint requires authentication")


class TestUsersRoutes:
    """Test users CRUD from server.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_list_users(self, auth_token):
        """Test GET /api/users endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the admin user
        emails = [u["email"] for u in data]
        assert ADMIN_EMAIL in emails
        print(f"✓ Users list: {len(data)} users")
    
    def test_create_and_delete_user(self, auth_token):
        """Test user creation and deletion"""
        test_email = f"TEST_user_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create user
        response = requests.post(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "email": test_email,
                "first_name": "Test",
                "last_name": "User",
                "password": "TestPass123!",
                "role": "user"
            }
        )
        assert response.status_code == 200
        user = response.json()
        assert user["email"] == test_email
        user_id = user["id"]
        print(f"✓ Created user: {test_email}")
        
        # Delete user
        response = requests.delete(
            f"{BASE_URL}/api/users/{user_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Deleted user: {test_email}")


class TestAppsRoutes:
    """Test apps CRUD from server.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_list_apps(self, auth_token):
        """Test GET /api/apps endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/apps",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Apps list: {len(data)} apps")


class TestRolesRoutes:
    """Test roles CRUD from server.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_list_roles(self, auth_token):
        """Test GET /api/roles endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/roles",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Roles list: {len(data)} roles")


class TestLaunchpadRoute:
    """Test launchpad endpoint from server.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_launchpad(self, auth_token):
        """Test GET /api/launchpad endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/launchpad",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "apps" in data
        print(f"✓ Launchpad: {len(data['apps'])} accessible apps")


class TestAuditLoggingCapture:
    """Test that audit logging captures create/update/delete actions"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_audit_log_captures_user_creation(self, auth_token):
        """Test that creating a user generates an audit log entry"""
        test_email = f"TEST_audit_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create user
        response = requests.post(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "email": test_email,
                "first_name": "Audit",
                "last_name": "Test",
                "password": "TestPass123!",
                "role": "user"
            }
        )
        assert response.status_code == 200
        user_id = response.json()["id"]
        
        # Check audit logs for the creation event
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=create&resource_type=user&limit=5",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        logs = response.json()["logs"]
        
        # Find the log entry for our user
        found = any(log["resource_id"] == user_id for log in logs)
        assert found, f"Audit log entry not found for user {user_id}"
        print(f"✓ Audit log captured user creation: {test_email}")
        
        # Cleanup - delete the user
        requests.delete(
            f"{BASE_URL}/api/users/{user_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_audit_log_captures_role_creation(self, auth_token):
        """Test that creating a role generates an audit log entry"""
        test_role_name = f"TEST_Role_{uuid.uuid4().hex[:8]}"
        
        # Create role
        response = requests.post(
            f"{BASE_URL}/api/roles",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": test_role_name,
                "description": "Test role for audit logging"
            }
        )
        assert response.status_code == 200
        role_id = response.json()["id"]
        
        # Check audit logs
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=create&resource_type=role&limit=5",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        logs = response.json()["logs"]
        
        found = any(log["resource_id"] == role_id for log in logs)
        assert found, f"Audit log entry not found for role {role_id}"
        print(f"✓ Audit log captured role creation: {test_role_name}")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/roles/{role_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
