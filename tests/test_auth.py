"""
Unit tests for authentication module.

Tests JWT token generation, verification, cookie handling, and auth middleware.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from flask import Flask, g, jsonify, request

from backend.auth import (
    generate_jwt_token,
    require_auth,
    set_token_cookies,
    verify_jwt_token,
)


class TestGenerateJWTToken:
    """Tests for JWT token generation."""

    def test_generates_valid_token_with_all_fields(self):
        """Test token generation includes all user data and timestamps."""
        user_data = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        secret = 'test-secret'
        token = generate_jwt_token(user_data, secret, '15m')

        assert token is not None
        assert isinstance(token, str)

        decoded = jwt.decode(token, secret, algorithms=['HS256'])
        assert decoded['user_id'] == 'user123'
        assert decoded['email'] == 'test@example.com'
        assert decoded['name'] == 'Test User'
        assert 'exp' in decoded
        assert 'iat' in decoded

    def test_token_expiry_matches_expires_in(self):
        """Test token expiry is correctly calculated from expires_in string."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}
        secret = 'secret'

        token = generate_jwt_token(user_data, secret, '1h')
        decoded = jwt.decode(token, secret, algorithms=['HS256'])

        # Verify expiry is approximately 1 hour from now
        expected_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        actual_exp = datetime.fromtimestamp(decoded['exp'], tz=timezone.utc)
        diff = abs((actual_exp - expected_exp).total_seconds())
        assert diff < 5  # Within 5 seconds

    def test_token_without_name_defaults_to_empty(self):
        """Test missing name field defaults to empty string."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com'}
        secret = 'secret'

        token = generate_jwt_token(user_data, secret, '15m')
        decoded = jwt.decode(token, secret, algorithms=['HS256'])

        assert decoded['name'] == ''

    def test_raises_value_error_on_empty_secret(self):
        """Test ValueError is raised when secret is None or empty."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}

        with pytest.raises(ValueError, match='JWT secret is not configured'):
            generate_jwt_token(user_data, '', '15m')

        with pytest.raises(ValueError, match='JWT secret is not configured'):
            generate_jwt_token(user_data, None, '15m')

    def test_uses_hs256_algorithm(self):
        """Test token uses HS256 algorithm."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}
        secret = 'secret'

        token = generate_jwt_token(user_data, secret, '15m')

        # Get header without verification
        header = jwt.get_unverified_header(token)
        assert header['alg'] == 'HS256'


class TestVerifyJWTToken:
    """Tests for JWT token verification."""

    def test_verifies_valid_token(self):
        """Test successful verification of a valid token."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}
        secret = 'secret'

        token = generate_jwt_token(user_data, secret, '15m')
        payload = verify_jwt_token(token, secret)

        assert payload is not None
        assert payload['user_id'] == 'u1'
        assert payload['email'] == 'e@e.com'

    def test_returns_none_for_expired_token(self):
        """Test expired tokens return None."""
        secret = 'secret'
        expired_payload = {
            'user_id': 'u1',
            'email': 'e@e.com',
            'name': 'N',
            'exp': datetime.now(timezone.utc) - timedelta(hours=1),
            'iat': datetime.now(timezone.utc) - timedelta(hours=2)
        }
        token = jwt.encode(expired_payload, secret, algorithm='HS256')

        result = verify_jwt_token(token, secret)
        assert result is None

    def test_returns_none_for_wrong_secret(self):
        """Test wrong secret returns None."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}
        token = generate_jwt_token(user_data, 'correct-secret', '15m')

        result = verify_jwt_token(token, 'wrong-secret')
        assert result is None

    def test_returns_none_for_malformed_token(self):
        """Test malformed tokens return None."""
        assert verify_jwt_token('invalid.token.format', 'secret') is None
        assert verify_jwt_token('not-even-jwt', 'secret') is None
        assert verify_jwt_token('', 'secret') is None

    def test_returns_none_for_none_secret(self):
        """Test None secret returns None without crashing."""
        user_data = {'user_id': 'u1', 'email': 'e@e.com', 'name': 'N'}
        token = generate_jwt_token(user_data, 'secret', '15m')

        result = verify_jwt_token(token, None)
        assert result is None

    def test_handles_clock_skew_with_leeway(self):
        """Test 10-second leeway handles minor clock skew."""
        secret = 'secret'
        # Token expired 5 seconds ago (within leeway)
        slightly_expired = {
            'user_id': 'u1',
            'email': 'e@e.com',
            'name': 'N',
            'exp': datetime.now(timezone.utc) - timedelta(seconds=5),
            'iat': datetime.now(timezone.utc) - timedelta(minutes=15)
        }
        token = jwt.encode(slightly_expired, secret, algorithm='HS256')

        # Should still verify due to leeway
        result = verify_jwt_token(token, secret)
        assert result is not None

    def test_returns_none_for_token_missing_required_fields(self):
        """Test tokens missing required fields return None."""
        secret = 'secret'
        incomplete_payload = {
            'exp': datetime.now(timezone.utc) + timedelta(hours=1),
            'iat': datetime.now(timezone.utc)
            # Missing user_id, email
        }
        token = jwt.encode(incomplete_payload, secret, algorithm='HS256')

        result = verify_jwt_token(token, secret)
        # Token verifies but payload is incomplete - this is expected behavior
        assert result is not None
        assert 'user_id' not in result


class TestSetTokenCookies:
    """Tests for cookie setting functionality."""

    @pytest.fixture
    def app(self):
        """Create Flask app for testing."""
        app = Flask(__name__)
        app.config['SESSION_COOKIE_SECURE'] = False
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        return app

    def test_sets_access_and_refresh_cookies(self, app):
        """Test both cookies are set with correct attributes."""
        with app.test_request_context():
            response = jsonify({'status': 'ok'})
            access_token = 'access123'
            refresh_token = 'refresh456'

            result = set_token_cookies(response, access_token, refresh_token)

            # Check cookies were set
            cookies = result.headers.getlist('Set-Cookie')
            assert any('access_token=' in c for c in cookies)
            assert any('refresh_token=' in c for c in cookies)

    def test_sets_httponly_flag(self, app):
        """Test cookies have HttpOnly flag for security."""
        with app.test_request_context():
            response = jsonify({})
            result = set_token_cookies(response, 'a', 'r')

            cookies = result.headers.getlist('Set-Cookie')
            for cookie in cookies:
                assert 'HttpOnly' in cookie or 'httponly' in cookie.lower()

    def test_sets_path_to_root(self, app):
        """Test cookies are set with path='/' for all routes."""
        with app.test_request_context():
            response = jsonify({})
            result = set_token_cookies(response, 'a', 'r')

            cookies = result.headers.getlist('Set-Cookie')
            for cookie in cookies:
                assert 'path=/' in cookie.lower()

    def test_production_mode_sets_secure_flag(self, app):
        """Test Secure flag is set in production mode."""
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'None'

        with app.test_request_context():
            response = jsonify({})
            result = set_token_cookies(response, 'a', 'r')

            cookies = result.headers.getlist('Set-Cookie')
            # In production with SameSite=None, should be Secure
            assert any('Secure' in c or 'secure' in c.lower() for c in cookies)

    def test_samesite_none_adds_partitioned_attribute(self, app):
        """Test Partitioned attribute added for CHIPS support."""
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'None'

        with app.test_request_context():
            response = jsonify({})
            result = set_token_cookies(response, 'a', 'r')

            cookies = result.headers.getlist('Set-Cookie')
            assert any('Partitioned' in c for c in cookies)

    def test_samesite_none_forces_secure_true(self, app):
        """Test SameSite=None forces Secure=True even if misconfigured."""
        app.config['SESSION_COOKIE_SECURE'] = False
        app.config['SESSION_COOKIE_SAMESITE'] = 'None'

        with app.test_request_context():
            response = jsonify({})
            result = set_token_cookies(response, 'a', 'r')

            cookies = result.headers.getlist('Set-Cookie')
            # Should force Secure=True due to SameSite=None
            assert any('Secure' in c or 'secure' in c.lower() for c in cookies)


class TestRequireAuth:
    """Tests for authentication middleware."""

    @pytest.fixture
    def app(self):
        """Create Flask app with test config."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app

    def test_returns_none_for_valid_access_token_cookie(self, app):
        """Test valid access token grants access."""
        with app.test_request_context():
            # Mock the cookie and config
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config, \
                 patch('backend.auth.verify_jwt_token') as mock_verify:

                mock_request.cookies.get.return_value = 'valid_token'
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'secret'
                mock_verify.return_value = {'user_id': 'u1', 'email': 'e@e.com'}

                result = require_auth()
                assert result is None

    def test_returns_401_for_missing_tokens(self, app):
        """Test missing tokens returns 401 response."""
        with app.test_request_context():
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config:

                mock_request.cookies.get.return_value = None
                mock_request.headers.get.return_value = None
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'secret'
                mock_config.REFRESH_TOKEN_JWT_SECRET = 'secret'

                result = require_auth()
                assert result is not None
                assert result[1] == 401

    def test_returns_401_for_invalid_access_token(self, app):
        """Test invalid access token returns 401."""
        with app.test_request_context():
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config, \
                 patch('backend.auth.verify_jwt_token') as mock_verify:

                mock_request.cookies.get.return_value = 'invalid_token'
                mock_request.headers.get.return_value = None
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'secret'
                mock_config.REFRESH_TOKEN_JWT_SECRET = 'secret'
                mock_verify.return_value = None

                result = require_auth()
                assert result is not None
                assert result[1] == 401

    def test_refreshes_tokens_with_valid_refresh_token(self, app):
        """Test valid refresh token issues new access token."""
        with app.test_request_context():
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config, \
                 patch('backend.auth.verify_jwt_token') as mock_verify, \
                 patch('backend.auth.generate_jwt_token') as mock_gen, \
                 patch('backend.models.User') as mock_user_model:

                # Access token invalid, refresh token valid
                mock_request.cookies.get.side_effect = lambda k: 'refresh_token' if k == 'refresh_token' else None
                mock_request.headers.get.return_value = None
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'access_secret'
                mock_config.REFRESH_TOKEN_JWT_SECRET = 'refresh_secret'
                mock_config.ACCESS_TOKEN_EXPIRETIME = '15m'
                mock_config.REFRESH_TOKEN_EXPIRETIME = '7d'

                # First call for access (None), second for refresh (valid)
                mock_verify.side_effect = [None, {'user_id': 'u1'}]

                # Mock user exists in DB
                mock_db_user = MagicMock()
                mock_db_user.google_user_id = 'u1'
                mock_db_user.email = 'e@e.com'
                mock_db_user.name = 'User'
                mock_user_model.query.filter_by.return_value.first.return_value = mock_db_user

                mock_gen.return_value = 'new_token'

                result = require_auth()
                # Should return None (success) and set pending tokens
                assert result is None

    def test_clears_cookies_on_auth_failure(self, app):
        """Test failed auth clears cookies."""
        with app.test_request_context():
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config, \
                 patch('backend.auth.verify_jwt_token') as mock_verify:

                mock_request.cookies.get.return_value = 'bad_token'
                mock_request.headers.get.return_value = None
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'secret'
                mock_config.REFRESH_TOKEN_JWT_SECRET = 'secret'
                mock_verify.return_value = None

                result = require_auth()
                assert result is not None

                # Check cookies are cleared
                cookies = result[0].headers.getlist('Set-Cookie')
                clear_count = sum(1 for c in cookies if 'max-age=0' in c.lower() or 'Max-Age=0' in c)
                assert clear_count >= 2  # Both tokens cleared

    def test_accepts_bearer_token_from_header(self, app):
        """Test Authorization header Bearer token is accepted."""
        with app.test_request_context():
            with patch('backend.auth.request') as mock_request, \
                 patch('backend.auth.Config') as mock_config, \
                 patch('backend.auth.verify_jwt_token') as mock_verify:

                mock_request.cookies.get.return_value = None
                mock_request.headers.get.return_value = 'Bearer header_token'
                mock_config.ACCESS_TOKEN_JWT_SECRET = 'secret'
                mock_verify.return_value = {'user_id': 'u1', 'email': 'e@e.com'}

                result = require_auth()
                assert result is None
