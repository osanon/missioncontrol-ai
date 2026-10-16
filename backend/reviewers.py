"""Human reviewer identities.

For now each reviewer has a personal token in the environment:
    REVIEWERS=alice:<token>,bob:<token>
A legacy single REVIEW_TOKEN still works and is treated as the reviewer named "reviewer".
Later this module can resolve identities from Google/Microsoft sign-in instead; callers only
need `reviewer_for_token()` to return a reviewer name.
"""
import os
import re
import secrets

NAME = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,39}$')
# Names that identify the analyst workspace or AI agents; a human reviewer must never share them.
RESERVED = {'analyst', 'system'}
MIN_TOKEN = 24


def load_reviewers():
    """Return {name: token}. Raises RuntimeError on unsafe or malformed configuration."""
    reviewers = {}
    for entry in filter(None, (x.strip() for x in os.getenv('REVIEWERS', '').split(','))):
        name, sep, token = entry.partition(':')
        name, token = name.strip(), token.strip()
        if not sep or not NAME.match(name):
            raise RuntimeError('REVIEWERS entries must look like name:token, with a lowercase name (letters, digits, . _ -).')
        if name in RESERVED or name.startswith('agent'):
            raise RuntimeError(f'Reviewer name "{name}" is reserved for the analyst workspace or AI agents.')
        if name in reviewers:
            raise RuntimeError(f'Reviewer "{name}" is listed more than once in REVIEWERS.')
        reviewers[name] = token
    legacy = os.getenv('REVIEW_TOKEN', '')
    if legacy and 'reviewer' not in reviewers:
        reviewers['reviewer'] = legacy
    for name, token in reviewers.items():
        if len(token) < MIN_TOKEN:
            raise RuntimeError(f'The token for reviewer "{name}" must be a random value of at least {MIN_TOKEN} characters.')
    if len(set(reviewers.values())) != len(reviewers):
        raise RuntimeError('Each reviewer needs a different token.')
    if os.getenv('APP_TOKEN', '') in reviewers.values():
        raise RuntimeError('Use different analyst and reviewer tokens.')
    return reviewers


def reviewer_for_token(token):
    """Return the reviewer name for a token, or None. Compares against every token to keep timing uniform."""
    match = None
    for name, expected in load_reviewers().items():
        if secrets.compare_digest(token.encode(), expected.encode()):
            match = name
    return match
