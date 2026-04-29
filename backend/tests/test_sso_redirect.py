"""
Test SSO Redirect functionality for Identity & Employee Hub
Tests the redirect-based SSO flow for external apps (Pulse)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin.test@identity.hub"
ADMIN_PASSWORD = "SecureTest123!"

# Registered app for testing
REGISTERED_APP_URL = "https://pulse-app.example.com"
UNREGISTERED_APP_URL = "https://malicious-site.com"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestAuthLogin:
    """Test POST /api/auth/login endpoint"""
    
    def test_login_success_returns_access_token(self, api_client):
        """Login with valid credentials returns access token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "user" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        
        # Verify user data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "sysadmin"
    
    def test_login_invalid_credentials_returns_401(self, api_client):
        """Login with invalid credentials returns 401"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestValidateRedirect:
    """Test POST /api/auth/validate-redirect endpoint"""
    
    def test_validate_redirect_requires_auth(self, api_client):
        """Validate redirect endpoint requires authentication"""
        # Remove auth header if present
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": REGISTERED_APP_URL},
            headers=headers
        )
        
        assert response.status_code == 401
    
    def test_validate_redirect_allows_registered_app(self, authenticated_client):
        """Validate redirect allows registered app URL (Pulse App)"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": f"{REGISTERED_APP_URL}/callback"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == True
        assert data.get("reason") is None
    
    def test_validate_redirect_allows_registered_app_with_path(self, authenticated_client):
        """Validate redirect allows registered app URL with different paths"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": f"{REGISTERED_APP_URL}/auth/callback?state=abc123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] == True
    
    def test_validate_redirect_denies_unregistered_app(self, authenticated_client):
        """Validate redirect denies unregistered app URL"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": f"{UNREGISTERED_APP_URL}/callback"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == False
        assert data["reason"] is not None
        assert "not registered" in data["reason"].lower() or "not authorized" in data["reason"].lower()
    
    def test_validate_redirect_denies_invalid_url(self, authenticated_client):
        """Validate redirect denies malformed URLs"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": "not-a-valid-url"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == False
        assert data["reason"] is not None
    
    def test_validate_redirect_requires_https_for_non_localhost(self, authenticated_client):
        """Validate redirect requires HTTPS for non-localhost URLs"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": "http://pulse-app.example.com/callback"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == False
        assert "https" in data["reason"].lower()


class TestAppsEndpoint:
    """Test GET /api/apps endpoint"""
    
    def test_apps_requires_auth(self, api_client):
        """Apps endpoint requires authentication"""
        headers = {"Content-Type": "application/json"}
        response = requests.get(f"{BASE_URL}/api/apps", headers=headers)
        
        assert response.status_code == 401
    
    def test_apps_returns_registered_apps(self, authenticated_client):
        """Apps endpoint returns list of registered apps including Pulse App"""
        response = authenticated_client.get(f"{BASE_URL}/api/apps")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Find Pulse App
        pulse_app = next((app for app in data if app["name"] == "Pulse App"), None)
        assert pulse_app is not None, "Pulse App not found in apps list"
        
        # Verify Pulse App data
        assert pulse_app["url"] == REGISTERED_APP_URL
        assert pulse_app["is_active"] == True
    
    def test_apps_returns_correct_structure(self, authenticated_client):
        """Apps endpoint returns apps with correct structure"""
        response = authenticated_client.get(f"{BASE_URL}/api/apps")
        
        assert response.status_code == 200
        data = response.json()
        
        for app in data:
            assert "id" in app
            assert "name" in app
            assert "url" in app
            assert "is_active" in app


class TestSSORedirectFlow:
    """Test the complete SSO redirect flow"""
    
    def test_login_and_validate_redirect_flow(self, api_client):
        """Test complete flow: login -> validate redirect -> get token for redirect"""
        # Step 1: Login
        login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Step 2: Validate redirect URL
        validate_response = api_client.post(
            f"{BASE_URL}/api/auth/validate-redirect",
            json={"redirect_url": f"{REGISTERED_APP_URL}/callback"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert validate_response.status_code == 200
        assert validate_response.json()["allowed"] == True
        
        # Step 3: Token can be used for redirect (verify token is valid)
        verify_response = api_client.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["valid"] == True
        # Verify endpoint returns token payload directly (not nested user object)
        assert verify_data["email"] == ADMIN_EMAIL


class TestTokenVerification:
    """Test token verification for downstream apps"""
    
    def test_verify_token_returns_user_info(self, authenticated_client, auth_token):
        """Verify endpoint returns user info for valid token"""
        response = authenticated_client.get(f"{BASE_URL}/api/auth/verify")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == True
        # Verify endpoint returns token payload directly with email, user_id, etc.
        assert "email" in data
        assert data["email"] == ADMIN_EMAIL
    
    def test_verify_token_invalid_returns_false(self, api_client):
        """Verify endpoint returns valid=false for invalid token"""
        response = api_client.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": "Bearer invalid-token-here"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
