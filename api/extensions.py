from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # no global limit; apply per-route where needed
    storage_uri="memory://",
)
