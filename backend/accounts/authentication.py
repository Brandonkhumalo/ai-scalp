import jwt
import hashlib
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import copy
import logging

from .models import BlacklistedToken

logger = logging.getLogger(__name__)

User = get_user_model()

# Cache TTL for blacklist lookups (seconds)
BLACKLIST_CACHE_TTL = 60


def _blacklist_cache_key(token):
    """Generate a short cache key from a JWT token by hashing it."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    return f'blacklist:{token_hash}'


def mark_token_blacklisted(token):
    """Add a token to both the DB blacklist and the in-memory cache."""
    BlacklistedToken.objects.get_or_create(token=token)
    cache.set(_blacklist_cache_key(token), True, BLACKLIST_CACHE_TTL)


class JWTAuthentication(BaseAuthentication):

    @staticmethod
    def generate_token(payload):
        expiration = datetime.utcnow() + timedelta(days=30)
        token_payload = copy.deepcopy(payload)
        token_payload['exp'] = int(expiration.timestamp())
        token_payload['type'] = 'access_token'
        token_payload['id'] = str(payload['id'])

        return jwt.encode(token_payload, key=settings.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def generate_refresh_token(payload):
        expiration = datetime.utcnow() + timedelta(days=60)
        token_payload = copy.deepcopy(payload)
        token_payload['exp'] = int(expiration.timestamp())
        token_payload['type'] = 'refresh_token'
        token_payload['id'] = str(payload['id'])

        return jwt.encode(token_payload, key=settings.SECRET_KEY, algorithm='HS256')

    def extract_token(self, request):
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        return None

    def verify_token(self, payload, token_type='access_token'):
        if 'exp' not in payload:
            raise InvalidTokenError("Token has no expiration")

        exp_timestamp = payload['exp']
        current_timestamp = int(datetime.utcnow().timestamp())

        if current_timestamp > exp_timestamp:
            raise ExpiredSignatureError("Token has expired")

        if payload.get('type') != token_type:
            raise InvalidTokenError(f"Expected token type '{token_type}', got '{payload.get('type')}'")

    def authenticate(self, request):
        token = self.extract_token(request)
        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            self.verify_token(payload, token_type='access_token')

            # Cache-first blacklist check: avoids a DB query on every request
            cache_key = _blacklist_cache_key(token)
            is_blacklisted = cache.get(cache_key)
            if is_blacklisted is None:
                # Cache miss — fall back to DB, then cache the result
                is_blacklisted = BlacklistedToken.objects.filter(token=token).exists()
                cache.set(cache_key, is_blacklisted, BLACKLIST_CACHE_TTL)
            if is_blacklisted:
                raise AuthenticationFailed("Token has been blacklisted.")

            user_id = payload.get('id')
            if not user_id:
                raise AuthenticationFailed("Token missing user ID.")

            user = User.objects.get(id=user_id)

            return (user, token)

        except (InvalidTokenError, ExpiredSignatureError, User.DoesNotExist, jwt.DecodeError) as e:
            raise AuthenticationFailed(f"Invalid Token: {str(e)}")
