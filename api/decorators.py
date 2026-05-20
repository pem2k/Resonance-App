from flask import session, jsonify


def require_admin():
    """
    Blueprint before_request hook.
    Returns 401 if the request has no valid admin session.
    Register on any blueprint that should be admin-only:

        blueprint.before_request(require_admin)
    """
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401
