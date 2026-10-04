"""Sign-in wall: /api/ requests need a Google ID token for an email in MONI_ALLOWED_EMAILS."""
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

from flask import Flask  # noqa: E402

from common.config_manager import ConfigManager  # noqa: E402
from web.routes import auth, register_routes  # noqa: E402

# Fake tokens -> the claims Google would return for them; anything else is "invalid".
TOKENS = {
    "allowed": {"email": "Boss@Example.com", "email_verified": True},
    "stranger": {"email": "stranger@example.com", "email_verified": True},
    "unverified": {"email": "boss@example.com", "email_verified": False},
}


def fake_verify(token, client_id):
    assert client_id == "web-client"
    if token not in TOKENS:
        raise ValueError("bad token")
    return TOKENS[token]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MONI_WEB_CLIENT_ID", "web-client")
    monkeypatch.setenv("MONI_ALLOWED_EMAILS", " boss@example.com , other@example.com")
    monkeypatch.setattr(auth, "_verify_google_token", fake_verify)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "model_name": "", "model_provider": None, "mailing_list": ["a@example.com"],
        "last_master_update": None, "last_master_filename": None,
        "schedule": [], "programs": [],
    }))
    app = Flask(__name__)
    app.config["config_manager"] = ConfigManager(str(cfg))
    app.config["files_dir"] = tmp_path
    register_routes(app)
    return app.test_client()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_header_is_401(client):
    assert client.get("/api/v1/mailing_list").status_code == 401


def test_non_bearer_header_is_401(client):
    r = client.get("/api/v1/mailing_list", headers={"Authorization": "Basic allowed"})
    assert r.status_code == 401


def test_invalid_token_is_401(client):
    assert client.get("/api/v1/mailing_list", headers=bearer("forged")).status_code == 401


def test_email_not_on_list_is_403(client):
    assert client.get("/api/v1/mailing_list", headers=bearer("stranger")).status_code == 403


def test_unverified_email_is_403(client):
    assert client.get("/api/v1/mailing_list", headers=bearer("unverified")).status_code == 403


def test_allowed_email_gets_through_case_insensitive(client):
    r = client.get("/api/v1/mailing_list", headers=bearer("allowed"))
    assert r.status_code == 200
    assert r.get_json() == ["a@example.com"]


def test_writes_are_guarded_too(client):
    r = client.post("/api/v1/mailing_list", json=["x@example.com"])
    assert r.status_code == 401
    r = client.post("/api/v1/mailing_list", json=["x@example.com"], headers=bearer("allowed"))
    assert r.status_code == 201


def test_me_returns_signed_in_email(client):
    r = client.get("/api/v1/auth/me", headers=bearer("allowed"))
    assert r.get_json() == {"email": "boss@example.com"}


def test_config_is_public(client):
    r = client.get("/api/v1/auth/config")
    assert r.status_code == 200
    assert r.get_json() == {"client_id": "web-client"}


def test_missing_client_id_fails_closed(client, monkeypatch):
    monkeypatch.delenv("MONI_WEB_CLIENT_ID")
    assert client.get("/api/v1/mailing_list", headers=bearer("allowed")).status_code == 401


def test_empty_allow_list_lets_nobody_in(client, monkeypatch):
    monkeypatch.setenv("MONI_ALLOWED_EMAILS", "")
    assert client.get("/api/v1/mailing_list", headers=bearer("allowed")).status_code == 403
