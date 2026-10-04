"""Sign-in wall: every /api/ request must carry a Google ID token for an allowed account.

The browser signs in with Google (public/login.html) and sends the ID token as
`Authorization: Bearer <token>`. We verify it against MONI_WEB_CLIENT_ID and let the
request through only if the email is in MONI_ALLOWED_EMAILS. Both live only in .env.
"""
import logging

from flask import Blueprint, g, jsonify, request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from common.config_manager import ConfigManager

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/api/v1/auth/config"}


def error_response(message: str, status_code: int = 400):
    return jsonify({"error": message, "message": message}), status_code

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def _verify_google_token(token: str, client_id: str) -> dict:
    """Checks signature, expiry, issuer and audience; raises ValueError if any fail."""
    return id_token.verify_oauth2_token(token, google_requests.Request(), audience=client_id)


def verify_request():
    """before_request guard. Returns None to let the request through, or a 401/403 response."""
    if request.method == "OPTIONS" or not request.path.startswith("/api/"):
        return None
    if request.path in PUBLIC_PATHS:
        return None

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not header[len("Bearer "):].strip():
        return error_response("נדרשת התחברות.", 401)

    client_id = ConfigManager.get_web_client_id()
    if not client_id:
        logger.warning("MONI_WEB_CLIENT_ID is not set in .env — rejecting every API request.")
        return error_response("ההתחברות לא הוגדרה בשרת.", 401)

    try:
        claims = _verify_google_token(header[len("Bearer "):].strip(), client_id)
    except ValueError:
        return error_response("ההתחברות פגה או אינה תקינה. יש להתחבר מחדש.", 401)

    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        return error_response("החשבון אינו מורשה.", 403)
    if email not in ConfigManager.get_allowed_emails():
        return error_response("החשבון אינו מורשה.", 403)

    g.user_email = email
    return None


@auth_bp.route("/config", methods=["GET"])
def get_auth_config():
    """Public: the login page needs the client id to render Google's button."""
    return jsonify({"client_id": ConfigManager.get_web_client_id() or ""})


@auth_bp.route("/me", methods=["GET"])
def get_me():
    return jsonify({"email": g.user_email})
