from flask import Blueprint, jsonify, request, session
from api.extensions import limiter
from api.models import AdminUser

auth = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth.route("/login", methods=["POST"])
@limiter.limit("10 per minute; 30 per hour")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    user = AdminUser.query.filter_by(username=username).first()

    if user and user.check_password(password):
        session.permanent = True
        session["is_admin"] = True
        return jsonify({"ok": True})

    return jsonify({"error": "Invalid credentials"}), 401


@auth.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth.route("/me", methods=["GET"])
def me():
    return jsonify({"is_admin": bool(session.get("is_admin"))})
