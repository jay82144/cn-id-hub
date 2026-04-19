"""
Test suite for new features in Identity & Employee Hub v3.0
- Email service endpoints
- Migration tracking endpoints
- Company app allocations
- Company branding
- Sysadmin company switcher (users endpoint with company_name)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://employee-hub-283.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin.test@identity.hub"
ADMIN_PASSWORD = "SecureTest123!"

# Test company IDs
ACME_CORP_ID = "0643f219-27ad-4c1b-b52f-4d09bfcc1bff"
TECHSTART_ID = "02b5ca32-6001-4990-9183-b6e031144f45"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for sysadmin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestEmailService:
    """Email service endpoint tests"""
    
    def test_email_status(self, auth_headers):
        """GET /api/email/status - Check email service status"""
        response = requests.get(f"{BASE_URL}/api/email/status", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "configured" in data
        assert "provider" in data
        assert "sender_email" in data
        assert "message" in data
        # Should be in mock mode (no RESEND_API_KEY)
        assert data["provider"] == "mock"
        assert data["configured"] == False
        print(f"Email status: {data['message']}")
    
    def test_email_templates(self, auth_headers):
        """GET /api/email/templates - List available templates"""
        response = requests.get(f"{BASE_URL}/api/email/templates", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "templates" in data
        assert "description" in data
        
        # Verify expected templates exist
        expected_templates = ["magic_link", "password_reset", "welcome", "notification"]
        for template in expected_templates:
            assert template in data["templates"], f"Missing template: {template}"
        print(f"Available templates: {data['templates']}")
    
    def test_email_send_mock(self, auth_headers):
        """POST /api/email/send - Send email in mock mode"""
        response = requests.post(
            f"{BASE_URL}/api/email/send",
            headers=auth_headers,
            json={
                "to": ["test@example.com"],
                "subject": "Test Email from pytest",
                "html": "<p>This is a test email</p>"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["mock"] == True
        assert "email_id" in data
        assert data["email_id"].startswith("mock_")
        print(f"Mock email sent: {data['email_id']}")
    
    def test_email_send_with_template(self, auth_headers):
        """POST /api/email/send - Send email using template"""
        response = requests.post(
            f"{BASE_URL}/api/email/send",
            headers=auth_headers,
            json={
                "to": ["user@example.com"],
                "subject": "Welcome!",
                "template": "welcome",
                "template_data": {
                    "app_name": "Identity Hub",
                    "first_name": "Test User",
                    "login_url": "https://example.com/login"
                }
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["mock"] == True
        print("Template email sent successfully")
    
    def test_email_send_requires_auth(self):
        """POST /api/email/send - Should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/email/send",
            json={"to": ["test@example.com"], "subject": "Test", "html": "<p>Test</p>"}
        )
        assert response.status_code == 401


class TestMigrationEndpoints:
    """Migration tracking endpoint tests"""
    
    def test_migration_status(self, auth_headers):
        """GET /api/admin/migrations - Get migration status"""
        response = requests.get(f"{BASE_URL}/api/admin/migrations", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "current_revision" in data
        assert "total_migrations" in data
        assert "applied_count" in data
        assert "pending_count" in data
        assert "is_up_to_date" in data
        assert "applied_migrations" in data
        assert "pending_migrations" in data
        
        # Should be up to date
        assert data["is_up_to_date"] == True
        assert data["pending_count"] == 0
        print(f"Current revision: {data['current_revision']}, Applied: {data['applied_count']}")
    
    def test_pending_migrations(self, auth_headers):
        """GET /api/admin/migrations/pending - Get pending migrations"""
        response = requests.get(f"{BASE_URL}/api/admin/migrations/pending", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "pending_count" in data
        assert "is_up_to_date" in data
        assert "migrations" in data
        
        # Should have no pending migrations
        assert data["pending_count"] == 0
        assert data["is_up_to_date"] == True
        print("No pending migrations")
    
    def test_schema_changelog(self, auth_headers):
        """GET /api/admin/schema/changelog - Get schema changelog"""
        response = requests.get(f"{BASE_URL}/api/admin/schema/changelog", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "changelog" in data
        assert "current_version" in data
        
        # Verify changelog structure
        assert len(data["changelog"]) >= 1
        for entry in data["changelog"]:
            assert "version" in entry
            assert "date" in entry
            assert "changes" in entry
        
        print(f"Current version: {data['current_version']}, Changelog entries: {len(data['changelog'])}")
    
    def test_upgrade_path(self, auth_headers):
        """GET /api/admin/schema/upgrade-path - Get upgrade instructions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/schema/upgrade-path",
            headers=auth_headers,
            params={"from_version": "1.0.0", "to_version": "3.0.0"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "from_version" in data
        assert "to_version" in data
        assert "changes" in data
        assert "migrations_needed" in data
        assert "recommendation" in data
        
        assert data["from_version"] == "1.0.0"
        assert data["to_version"] == "3.0.0"
        assert len(data["changes"]) > 0
        print(f"Upgrade path: {len(data['changes'])} changes, {len(data['migrations_needed'])} migrations")
    
    def test_migration_requires_sysadmin(self):
        """Migration endpoints should require sysadmin role"""
        response = requests.get(f"{BASE_URL}/api/admin/migrations")
        assert response.status_code == 401


class TestCompanyAppAllocations:
    """Company app allocation endpoint tests"""
    
    def test_list_company_apps(self, auth_headers):
        """GET /api/company-apps - List all allocations"""
        response = requests.get(f"{BASE_URL}/api/company-apps", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Should have at least one allocation (CRM Pro to Acme Corp)
        if len(data) > 0:
            allocation = data[0]
            assert "id" in allocation
            assert "company_id" in allocation
            assert "app_id" in allocation
            assert "is_active" in allocation
            assert "company_name" in allocation
            assert "app_name" in allocation
            print(f"Found {len(data)} app allocations")
    
    def test_list_company_apps_filtered(self, auth_headers):
        """GET /api/company-apps?company_id=X - Filter by company"""
        response = requests.get(
            f"{BASE_URL}/api/company-apps",
            headers=auth_headers,
            params={"company_id": ACME_CORP_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        # All results should be for Acme Corp
        for allocation in data:
            assert allocation["company_id"] == ACME_CORP_ID
        print(f"Acme Corp has {len(data)} app allocations")
    
    def test_create_and_delete_allocation(self, auth_headers):
        """POST /api/company-apps and DELETE - Create and remove allocation"""
        # First get an app that's not allocated to TechStart
        apps_response = requests.get(f"{BASE_URL}/api/apps", headers=auth_headers)
        apps = apps_response.json()
        
        if len(apps) == 0:
            pytest.skip("No apps available for testing")
        
        app_id = apps[0]["id"]
        
        # Try to create allocation for TechStart
        create_response = requests.post(
            f"{BASE_URL}/api/company-apps",
            headers=auth_headers,
            json={
                "company_id": TECHSTART_ID,
                "app_id": app_id
            }
        )
        
        # May fail if already allocated
        if create_response.status_code == 400:
            print("App already allocated to TechStart, skipping create test")
            return
        
        assert create_response.status_code == 200
        allocation = create_response.json()
        allocation_id = allocation["id"]
        print(f"Created allocation: {allocation_id}")
        
        # Delete the allocation
        delete_response = requests.delete(
            f"{BASE_URL}/api/company-apps/{allocation_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        print("Allocation deleted successfully")
    
    def test_company_apps_requires_sysadmin(self):
        """Company apps endpoints require sysadmin"""
        response = requests.get(f"{BASE_URL}/api/company-apps")
        assert response.status_code == 401


class TestCompanyBranding:
    """Company branding endpoint tests"""
    
    def test_get_company_branding_public(self):
        """GET /api/companies/{id}/branding - Public endpoint"""
        response = requests.get(f"{BASE_URL}/api/companies/{ACME_CORP_ID}/branding")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "logo_url" in data
        assert "primary_color" in data
        assert "secondary_color" in data
        
        assert data["name"] == "Acme Corp"
        print(f"Branding: {data['name']}, Primary: {data['primary_color']}")
    
    def test_update_my_branding_requires_company(self, auth_headers):
        """PUT /api/companies/my/branding - Requires company association"""
        # Sysadmin without company should get error
        response = requests.put(
            f"{BASE_URL}/api/companies/my/branding",
            headers=auth_headers,
            json={"primary_color": "#FF0000"}
        )
        assert response.status_code == 400
        assert "not associated with a company" in response.json()["detail"]
        print("Correctly rejected sysadmin without company")


class TestUsersWithCompanyName:
    """Test that users endpoint shows company names for sysadmin"""
    
    def test_list_users_shows_company_name(self, auth_headers):
        """GET /api/users - Should include company_name field"""
        response = requests.get(f"{BASE_URL}/api/users", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Check that company_name field exists
        if len(data) > 0:
            user = data[0]
            assert "company_name" in user, "company_name field missing from user response"
            print(f"Users list includes company_name field")
    
    def test_list_users_filter_by_company(self, auth_headers):
        """GET /api/users?company_id=X - Filter users by company"""
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers=auth_headers,
            params={"company_id": ACME_CORP_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        # All users should be from Acme Corp (or have null company)
        for user in data:
            if user["company_id"]:
                assert user["company_id"] == ACME_CORP_ID
        print(f"Filtered users by company: {len(data)} results")


class TestCompaniesEndpoint:
    """Test companies endpoint for sysadmin company switcher"""
    
    def test_list_companies(self, auth_headers):
        """GET /api/companies - List all companies"""
        response = requests.get(f"{BASE_URL}/api/companies", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # Should have Acme Corp and TechStart Inc
        
        company_names = [c["name"] for c in data]
        assert "Acme Corp" in company_names
        assert "TechStart Inc" in company_names
        print(f"Found {len(data)} companies: {company_names}")
    
    def test_companies_requires_sysadmin(self):
        """GET /api/companies - Requires sysadmin"""
        response = requests.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
