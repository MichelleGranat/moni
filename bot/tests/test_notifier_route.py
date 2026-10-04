"""/api/v1/notifier — read-only: reports the .env sender and whether Gmail OAuth is set up."""
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

from flask import Flask  # noqa: E402

from common.config_manager import ConfigManager  # noqa: E402
from web.routes import auth, register_routes  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Signed in as an allowed user; the sign-in wall itself is covered in test_web_auth.py.
    monkeypatch.setenv("MONI_WEB_CLIENT_ID", "web-client")
    monkeypatch.setenv("MONI_ALLOWED_EMAILS", "boss@example.com")
    monkeypatch.setattr(auth, "_verify_google_token",
                        lambda token, client_id: {"email": "boss@example.com", "email_verified": True})
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "model_name": "", "model_provider": None, "mailing_list": [],
        "last_master_update": None, "last_master_filename": None,
        "schedule": [], "programs": [],
    }))
    app = Flask(__name__)
    app.config["config_manager"] = ConfigManager(str(cfg))
    app.config["files_dir"] = tmp_path
    register_routes(app)
    test_client = app.test_client()
    test_client.environ_base["HTTP_AUTHORIZATION"] = "Bearer token"
    return test_client


def test_get_reports_env_sender(client, monkeypatch):
    monkeypatch.setenv("MONI_SENDER", "env@example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "1//refresh")
    r = client.get("/api/v1/notifier")
    assert r.status_code == 200
    assert r.get_json() == {"email": "env@example.com", "configured": True}


def test_get_reports_unconfigured(client, monkeypatch):
    monkeypatch.delenv("MONI_SENDER", raising=False)
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    r = client.get("/api/v1/notifier")
    assert r.get_json() == {"email": "", "configured": False}


def test_post_is_rejected(client):
    r = client.post("/api/v1/notifier", json={"email": "x@example.com", "password": "p"})
    assert r.status_code == 405


def test_get_not_configured_without_refresh_token(client, monkeypatch):
    monkeypatch.setenv("MONI_SENDER", "env@example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
    assert client.get("/api/v1/notifier").get_json()["configured"] is False
