"""Browser sessions and the public demo.

After signing in with the analyst token (and optionally a personal reviewer token) the browser holds a signed,
HttpOnly cookie, so tokens never stay in page memory and a reload keeps you signed in. The cookie stores the
reviewer's name, not their token; the name is re-checked against REVIEWERS on every request, so removing a
reviewer takes effect immediately.

PUBLIC_DEMO=true adds one-click "Try as analyst / Try as reviewer" sessions for hackathon judges. Demo reviewer
decisions are recorded as "demo-reviewer". Use it only with the fictional dataset.
"""
import base64
import hashlib
import hmac
import json
import os
import time

COOKIE = 'mc_session'
LIFETIME = 12 * 3600
DEMO_REVIEWER = 'demo-reviewer'
CSRF_HEADER = 'x-requested-with'


def public_demo():
    return os.getenv('PUBLIC_DEMO', '').lower() in ('1', 'true', 'yes')


def secret():
    # A dedicated SESSION_SECRET is preferred; otherwise derive one from APP_TOKEN (rotating APP_TOKEN signs everyone out).
    value = os.getenv('SESSION_SECRET') or 'derived:' + os.getenv('APP_TOKEN', '')
    return hashlib.sha256(('mc-session:' + value).encode()).digest()


def _sign(body):
    return base64.urlsafe_b64encode(hmac.new(secret(), body.encode(), hashlib.sha256).digest()).decode().rstrip('=')


def encode(reviewer=None, demo=False, now=None):
    payload = {'v': 1, 'reviewer': reviewer, 'demo': demo, 'exp': int((now or time.time()) + LIFETIME)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    return body + '.' + _sign(body)


def decode(value, now=None):
    """Return the session payload, or None if missing, tampered, expired, or no longer valid."""
    if not value or value.count('.') != 1:
        return None
    body, signature = value.split('.')
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get('v') != 1 or not isinstance(payload.get('exp'), int) or payload['exp'] < (now or time.time()):
        return None
    if payload.get('demo') and not public_demo():
        return None
    return payload


def session_reviewer(payload):
    """The reviewer a session may act as, if any, re-checked against current configuration."""
    from backend.reviewers import load_reviewers
    name = payload and payload.get('reviewer')
    if not name:
        return None
    if payload.get('demo'):
        return name if name == DEMO_REVIEWER and public_demo() else None
    return name if name in load_reviewers() else None


def set_cookie(response, value):
    response.set_cookie(COOKIE, value, max_age=LIFETIME, httponly=True, samesite='strict', path='/',
                        secure=os.getenv('COOKIE_SECURE', '').lower() in ('1', 'true', 'yes'))


def clear_cookie(response):
    response.delete_cookie(COOKIE, path='/')
