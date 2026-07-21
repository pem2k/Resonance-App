from api.extensions import db


class AutoSyncState(db.Model):
    __tablename__ = "auto_sync_states"

    season_id = db.Column(
        db.Integer,
        db.ForeignKey("seasons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_started_at = db.Column(db.DateTime, nullable=True)
    last_completed_at = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(20), nullable=True)
    last_summary = db.Column(db.Text, nullable=True)

    season = db.relationship("Season")
