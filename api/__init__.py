import os
import click
from datetime import timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException
from api.extensions import db, limiter


_DIST = os.path.join(os.path.dirname(__file__), "..", "client", "dist")


def create_app(config=None):
    config = config or {}
    if not config.get("TESTING"):
        load_dotenv()

    app = Flask(__name__, static_folder=_DIST, static_url_path="")

    # ── Core config ──────────────────────────────────────────────────────────
    secret = config.get("SECRET_KEY") or os.environ.get("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("SECRET_KEY environment variable must be set.")
    app.config["SECRET_KEY"] = secret

    db_url = config.get("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL", "sqlite:///resonance.db")
    # Heroku-style URLs use the deprecated postgres:// scheme; SQLAlchemy 2.x
    # only accepts postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    is_sqlite = db_url.startswith("sqlite")

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if is_sqlite:
        # WAL mode lets reads proceed during long sync writes; busy_timeout avoids lock errors
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"timeout": 30},
            "pool_pre_ping": True,
        }
    else:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    app.config.update(config)

    # ── Session / cookie security ─────────────────────────────────────────────
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Only send the session cookie over HTTPS in production
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("APP_ENV") == "production"

    # ── CORS (credentials required for session cookies) ───────────────────────
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    CORS(app, supports_credentials=True, origins=allowed_origins)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    limiter.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from api.models import Season, Team, Player, Tournament, TournamentEntry, AdminUser  # noqa: F401
    from api.routes import public, admin, sync_bp, auth
    app.register_blueprint(public)
    app.register_blueprint(admin)
    app.register_blueprint(sync_bp)
    app.register_blueprint(auth)

    @app.errorhandler(HTTPException)
    def api_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": error.description}), error.code
        return error

    with app.app_context():
        db.create_all()
        if is_sqlite:
            # WAL mode allows concurrent reads during long sync writes
            db.session.execute(db.text("PRAGMA journal_mode=WAL"))
            db.session.execute(db.text("PRAGMA busy_timeout=10000"))
            db.session.commit()

    # ── CLI commands ──────────────────────────────────────────────────────────
    @app.cli.command("auto-sync")
    def auto_sync():
        """Sync all active seasons that have a sync window set. Run via Heroku Scheduler."""
        from api import sync as sync_service
        seasons = Season.query.filter_by(status="active").all()
        synced = 0
        for s in seasons:
            if s.sync_from and s.sync_to:
                click.echo(f"Syncing season: {s.name} …")
                result = sync_service.sync_season(s)
                click.echo(f"  done — {result}")
                synced += 1
        if not synced:
            click.echo("No active seasons with a sync window found.")

    @app.cli.command("create-admin")
    @click.argument("username")
    def create_admin(username):
        """Create or update an admin user. Prompts for password."""
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        with app.app_context():
            from api.models import AdminUser
            user = AdminUser.query.filter_by(username=username).first()
            if user:
                user.set_password(password)
                click.echo(f"Updated password for '{username}'.")
            else:
                user = AdminUser(username=username)
                user.set_password(password)
                db.session.add(user)
                click.echo(f"Admin user '{username}' created.")
            db.session.commit()

    # ── Serve React (catch-all — must be registered after API blueprints) ────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        full = os.path.join(app.static_folder, path)
        if path and os.path.exists(full):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    # ── Security headers on every response ────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app
