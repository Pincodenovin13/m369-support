"""Pure unit tests — no DB required."""
from __future__ import annotations

import uuid

import pytest

from app.security import (
    create_access_token,
    decode_access_token,
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
    token = create_access_token(subject=user_id, token_type="agency", agency_id=agency_id)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["agency_id"] == agency_id
    assert decoded["type"] == "agency"


def test_super_admin_token_round_trip():
    sa_id = str(uuid.uuid4())
    token = create_access_token(subject=sa_id, token_type="super_admin")
    decoded = decode_super_admin_token(token)
    assert decoded is not None
    assert decoded["sub"] == sa_id
    assert decoded["type"] == "super_admin"


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
