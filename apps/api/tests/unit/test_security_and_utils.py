"""Pure unit tests — no DB required."""
from __future__ import annotations

import uuid

import pytest

from app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_super_admin_token,
    hash_password,
    verify_password,
)
from app.slugs import slugify, unique_slug


def test_password_hash_round_trip():
    pw = "super-secret-password-123"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)


def test_password_hash_unique_per_call():
    pw = "same-password-123"
    assert hash_password(pw) != hash_password(pw)


def test_agency_token_round_trip():
    user_id = str(uuid.uuid4())
    agency_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, token_type="agency", agency_id=agency_id, token_version=0)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["agency_id"] == agency_id
    assert decoded["type"] == "agency"


def test_super_admin_token_round_trip():
    sa_id = str(uuid.uuid4())
    # token_version is required by the hardened create_access_token for SA tokens
    token = create_access_token(subject=sa_id, token_type="super_admin", token_version=0)
    decoded = decode_super_admin_token(token)
    assert decoded is not None
    assert decoded["sub"] == sa_id
    assert decoded["type"] == "super_admin"
    assert decoded["tver"] == 0


def test_garbage_token_rejected():
    assert decode_access_token("not.a.jwt") is None
    assert decode_access_token("") is None
    assert decode_super_admin_token("garbage") is None


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"
    assert slugify("Café Résumé") == "cafe-resume"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert slugify("") == "agency"
    assert slugify("---only-dashes---") == "only-dashes"
    assert slugify("Mixed CASE 123") == "mixed-case-123"


def test_slugify_unicode():
    assert slugify("سلام دنیا") == "agency"
    assert slugify("日本語") == "agency"
    assert slugify("Café 2026") == "cafe-2026"


# ---------------------------------------------------------------------------
# Refresh token — create_refresh_token tests
# ---------------------------------------------------------------------------


def test_create_agency_refresh_token_with_valid_agency_id():
    """create_refresh_token with agency_id + token_version succeeds."""
    user_id = str(uuid.uuid4())
    agency_id = str(uuid.uuid4())
    token = create_refresh_token(subject=user_id, token_type="agency", agency_id=agency_id, token_version=0)
    decoded = decode_refresh_token(token, expected_scope="agency")
    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["scope"] == "agency"
    assert decoded["agency_id"] == agency_id
    assert decoded["type"] == "refresh"
    assert decoded["tver"] == 0


def test_create_refresh_token_rejects_super_admin():
    """create_refresh_token with token_type='super_admin' must raise ValueError."""
    with pytest.raises(ValueError, match="only supports token_type='agency'"):
        create_refresh_token(subject=str(uuid.uuid4()), token_type="super_admin")


def test_create_refresh_token_rejects_missing_agency_id():
    """create_refresh_token with agency token_type but no agency_id must raise ValueError."""
    with pytest.raises(ValueError, match="agency_id is required"):
        create_refresh_token(subject=str(uuid.uuid4()), token_type="agency", agency_id=None)


def test_create_refresh_token_rejects_missing_token_version():
    """create_refresh_token with agency token_type but no token_version must raise ValueError."""
    with pytest.raises(ValueError, match="token_version is required"):
        create_refresh_token(subject=str(uuid.uuid4()), token_type="agency", agency_id=str(uuid.uuid4()))
