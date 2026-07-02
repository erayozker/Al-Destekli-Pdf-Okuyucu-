from __future__ import annotations

from flask import Flask, Response
from dotenv import load_dotenv

from .config import IS_PRODUCTION, MAX_CONTENT_LENGTH, SECRET_KEY
from .filters import render_highlights
from .repository import init_db, load_documents
from .routes import bp


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
    app.config["JSON_AS_ASCII"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.json.ensure_ascii = False
    app.jinja_env.filters["render_highlights"] = render_highlights
    app.register_blueprint(bp)

    @app.after_request
    def ensure_utf8(response: Response) -> Response:
        if response.mimetype.startswith("text/") and "charset" not in response.content_type.lower():
            response.content_type = f"{response.mimetype}; charset=utf-8"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    init_db()
    load_documents()
    return app
