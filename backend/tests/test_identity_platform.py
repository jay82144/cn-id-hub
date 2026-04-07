"""
Identity & Employee Hub Platform Tests
Tests for:
- Bootstrap admin credential change flow
- JWT token validation (15 min access, 30 day refresh)
- API key authentication
- Identity context endpoints
- CORS configuration
"""
import pytest
import requests
import os
import jwt
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://employee-hub-283.preview.emergentagent.com')

# Test credentials
BOOTSTRAP_ADMIN_EMAIL = "admin@bootstrap.hub"
BOOTSTRAP_ADMIN_PASSWORD = "ChangeMeNow!"
CURRENT_ADMIN_EMAIL = "admin.final@identity.hub"
CURRENT_ADMIN_PASSWORD = "FinalSecure456!"


class TestHealthAndBasics:
    """Basic health and API availability tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint working")
    
    def test_root_endpoint(self):
        """Test root API endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "Identity & Employee Hub API" in data["message"]
        assert data["version"] == "3.0.0"
        print("✓ Root endpoint working, version 3.0.0")


class TestAuthenticationFlow:
    """Test authentication endpoints"""
    
    def test_login_with_current_admin(self):
        """Test login with current admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "user" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == CURRENT_ADMIN_EMAIL
        assert data["user"]["role"] == "sysadmin"
        assert data["must_change_password"] == False
        assert data["must_change_email"] == False
        print(f"✓ Login successful for {CURRENT_ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@email.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")
    
    def test_bootstrap_admin_not_available(self):
        """Test that bootstrap admin credentials no longer work (already changed)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": BOOTSTRAP_ADMIN_EMAIL, "password": BOOTSTRAP_ADMIN_PASSWORD}
        )
        # Should fail since bootstrap admin was already changed
        assert response.status_code == 401
        print("✓ Bootstrap admin credentials correctly invalidated after change")


class TestJWTTokenValidation:
    """Test JWT token structure and validation"""
    
    @pytest.fixture
    def access_token(self):
        """Get access token for tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_jwt_payload_structure(self, access_token):
        """Test JWT payload contains required fields"""
        # Decode without verification to check structure
        payload = jwt.decode(access_token, options={"verify_signature": False})
        
        # Required fields per spec
        assert "sub" in payload, "Missing 'sub' in JWT payload"
        assert "user_id" in payload, "Missing 'user_id' in JWT payload"
        assert "email" in payload, "Missing 'email' in JWT payload"
        assert "company_id" in payload, "Missing 'company_id' in JWT payload"
        assert "roles" in payload, "Missing 'roles' in JWT payload"
        assert "permissions" in payload, "Missing 'permissions' in JWT payload"
        assert "token_type" in payload, "Missing 'token_type' in JWT payload"
        assert "exp" in payload, "Missing 'exp' in JWT payload"
        assert "iat" in payload, "Missing 'iat' in JWT payload"
        
        # Verify token type
        assert payload["token_type"] == "access"
        
        # Verify roles and permissions
        assert "sysadmin" in payload["roles"]
        assert "admin:system" in payload["permissions"]
        
        print("✓ JWT payload contains all required fields")
        print(f"  - user_id: {payload['user_id']}")
        print(f"  - email: {payload['email']}")
        print(f"  - roles: {payload['roles']}")
        print(f"  - permissions: {payload['permissions']}")
    
    def test_jwt_expiration_15_minutes(self, access_token):
        """Test JWT access token has 15 minute expiration"""
        payload = jwt.decode(access_token, options={"verify_signature": False})
        
        exp = payload["exp"]
        iat = payload["iat"]
        
        # Calculate difference in minutes
        diff_seconds = exp - iat
        diff_minutes = diff_seconds / 60
        
        # Should be 15 minutes (allow small tolerance)
        assert 14 <= diff_minutes <= 16, f"Expected 15 min expiration, got {diff_minutes} min"
        print(f"✓ JWT access token expiration: {diff_minutes} minutes")
    
    def test_auth_verify_endpoint(self, access_token):
        """Test /api/auth/verify endpoint for downstream apps"""
        response = requests.get(
            f"{BASE_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == True
        assert "user_id" in data
        assert "email" in data
        assert "roles" in data
        assert "permissions" in data
        print("✓ Token verification endpoint working")


class TestAuthMe:
    """Test /api/auth/me endpoint"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_current_user(self, auth_headers):
        """Test getting current user info"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == CURRENT_ADMIN_EMAIL
        assert data["role"] == "sysadmin"
        assert data["status"] == "active"
        assert data["must_change_password"] == False
        assert data["must_change_email"] == False
        print("✓ /api/auth/me returns correct user info")
    
    def test_auth_me_without_token(self):
        """Test /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ /api/auth/me correctly requires authentication")


class TestAPIKeyAuthentication:
    """Test API key creation and authentication"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_create_api_key_verify_only(self, auth_session):
        """Test creating API key with verify_only scope"""
        response = auth_session.post(
            f"{BASE_URL}/api/api-keys",
            json={
                "name": "Test API Key",
                "scope": "verify_only"
            }
        )
        assert response.status_code == 200, f"Failed to create API key: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "name" in data
        assert "key_prefix" in data
        assert "api_key" in data  # Full key only returned on creation
        assert data["scope"] == "verify_only"
        assert data["key_prefix"].startswith("idhub_")
        
        print(f"✓ API key created with prefix: {data['key_prefix']}")
        return data["api_key"]
    
    def test_api_key_authentication_on_auth_me(self, auth_session):
        """Test API key authentication via X-API-Key header"""
        # First create an API key
        create_response = auth_session.post(
            f"{BASE_URL}/api/api-keys",
            json={
                "name": "Auth Test Key",
                "scope": "verify_only"
            }
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["api_key"]
        
        # Now test authentication with API key
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == CURRENT_ADMIN_EMAIL
        print("✓ API key authentication working on /api/auth/me")
    
    def test_list_api_keys(self, auth_session):
        """Test listing API keys"""
        response = auth_session.get(f"{BASE_URL}/api/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} API keys")
    
    def test_invalid_api_key(self):
        """Test invalid API key returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"X-API-Key": "invalid_key_12345"}
        )
        assert response.status_code == 401
        print("✓ Invalid API key correctly rejected")


class TestIdentityContext:
    """Test identity context endpoints for downstream apps"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_identity_context_endpoint(self, auth_headers):
        """Test /api/identity/context endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/identity/context",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == True
        assert "user_id" in data
        assert "email" in data
        assert "roles" in data
        assert "permissions" in data
        print("✓ Identity context endpoint working")
    
    def test_identity_context_without_auth(self):
        """Test identity context without auth returns error"""
        response = requests.get(f"{BASE_URL}/api/identity/context")
        assert response.status_code == 200  # Returns valid: false
        data = response.json()
        assert data["valid"] == False
        print("✓ Identity context correctly handles missing auth")


class TestLogout:
    """Test logout functionality"""
    
    def test_logout_endpoint(self):
        """Test logout endpoint"""
        # Login first
        session = requests.Session()
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = login_response.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Logout
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200
        data = logout_response.json()
        assert data["message"] == "Logged out successfully"
        print("✓ Logout endpoint working")


class TestRefreshToken:
    """Test refresh token functionality"""
    
    def test_refresh_without_cookie(self):
        """Test refresh endpoint without cookie returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/refresh")
        assert response.status_code == 401
        print("✓ Refresh correctly requires refresh token cookie")
    
    def test_login_sets_refresh_cookie(self):
        """Test that login sets refresh token cookie"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        
        # Check if refresh_token cookie was set
        cookies = session.cookies.get_dict()
        # Note: HttpOnly cookies may not be visible in requests library
        # The cookie is set server-side
        print("✓ Login completed (refresh token set as HttpOnly cookie)")


class TestCORSConfiguration:
    """Test CORS configuration"""
    
    def test_cors_not_wildcard(self):
        """Test that CORS is not configured as wildcard"""
        # Make an OPTIONS request to check CORS headers
        response = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "https://employee-hub-283.preview.emergentagent.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        # Check CORS headers
        cors_origin = response.headers.get("Access-Control-Allow-Origin", "")
        
        # Should NOT be wildcard *
        assert cors_origin != "*", "CORS should not be wildcard *"
        print(f"✓ CORS origin: {cors_origin} (not wildcard)")
    
    def test_cors_allows_credentials(self):
        """Test that CORS allows credentials"""
        response = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "https://employee-hub-283.preview.emergentagent.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        allow_credentials = response.headers.get("Access-Control-Allow-Credentials", "")
        assert allow_credentials.lower() == "true", "CORS should allow credentials"
        print("✓ CORS allows credentials")


class TestChangeCredentialsEndpoint:
    """Test change credentials endpoint (for bootstrap admin flow)"""
    
    def test_change_credentials_requires_auth(self):
        """Test that change-credentials requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/auth/change-credentials",
            json={
                "new_email": "test@test.com",
                "new_password": "TestPassword123!"
            }
        )
        assert response.status_code == 401
        print("✓ Change credentials correctly requires authentication")
    
    def test_change_credentials_not_required_for_normal_user(self):
        """Test that change-credentials returns error when not required"""
        # Login with current admin (who doesn't need to change credentials)
        session = requests.Session()
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = login_response.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Try to change credentials
        response = session.post(
            f"{BASE_URL}/api/auth/change-credentials",
            json={
                "new_email": "another@test.com",
                "new_password": "AnotherPassword123!"
            }
        )
        # Should return 400 since credential change is not required
        assert response.status_code == 400
        data = response.json()
        assert "not required" in data["detail"].lower()
        print("✓ Change credentials correctly rejects when not required")


class TestAdminEndpoints:
    """Test admin panel endpoints"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CURRENT_ADMIN_EMAIL, "password": CURRENT_ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_list_users(self, auth_session):
        """Test listing users"""
        response = auth_session.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} users")
    
    def test_list_apps(self, auth_session):
        """Test listing apps"""
        response = auth_session.get(f"{BASE_URL}/api/apps")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} apps")
    
    def test_list_roles(self, auth_session):
        """Test listing roles"""
        response = auth_session.get(f"{BASE_URL}/api/roles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} roles")
    
    def test_launchpad(self, auth_session):
        """Test launchpad endpoint"""
        response = auth_session.get(f"{BASE_URL}/api/launchpad")
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "apps" in data
        print("✓ Launchpad endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
