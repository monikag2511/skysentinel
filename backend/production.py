"""One-origin deployment entry point. Put a TLS reverse proxy in front of it."""
import base64
import binascii
import hmac
import os
from pathlib import Path

from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from main import create_app


def production_app(engine=None, assets=None):
    accounts = {}
    for role in ("operator", "viewer"):
        secret = os.getenv(f"SKY_{role.upper()}_PASSWORD", "")
        if len(secret) < 20:
            raise RuntimeError(f"Configure SKY_{role.upper()}_PASSWORD with at least 20 characters")
        accounts[role] = secret.encode()
    if accounts["operator"] == accounts["viewer"]:
        raise RuntimeError("Viewer and operator must use distinct passwords")
    app = create_app(engine, docs=False)

    @app.middleware("http")
    async def authorize(request, call_next):
        if request.url.path in ("/health/live", "/health/ready"):
            return await call_next(request)
        method, _, token = request.headers.get("authorization", "").partition(" ")
        user, password = b"", b""
        if method.lower() == "basic":
            try:
                user, _, password = base64.b64decode(token, validate=True).partition(b":")
            except (ValueError, binascii.Error):
                pass
        role = user.decode("ascii", errors="replace")
        if not hmac.compare_digest(accounts.get(role, b"invalid-user"), password) or role not in accounts:
            return JSONResponse({"detail": "Sign in to flight control"}, 401,
                                headers={"WWW-Authenticate": 'Basic realm="SkySentinel", charset="UTF-8"',
                                         "Cache-Control": "no-store"})
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if role != "operator" or request.headers.get("X-Sky-Command") != "1":
                return JSONResponse({"detail": "Operator credentials and command header required"}, 403)
        request.state.role = role
        response = await call_next(request)
        response.headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                                 "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    dist = Path(assets) if assets else Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise RuntimeError("Build the React client before starting production")
    app.mount("/", StaticFiles(directory=dist, html=True), name="console")
    return app
