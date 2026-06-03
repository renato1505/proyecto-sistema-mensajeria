import hmac
import secrets

from flask import abort, request, session


def obtener_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validar_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    token_sesion = session.get("_csrf_token", "")
    token_request = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")

    if not token_sesion or not token_request:
        abort(400)

    if not hmac.compare_digest(token_sesion, token_request):
        abort(400)
