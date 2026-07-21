from datetime import timezone

from api.extensions import db


class Tournament(db.Model):
    __tablename__ = "tournaments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    # start.gg identifiers — nullable until linked
    startgg_id = db.Column(db.String(50), nullable=True)
    startgg_slug = db.Column(db.String(200), nullable=True)
    total_entrants = db.Column(db.Integer, nullable=True)
    # Stamped after a successful start.gg sync; null = not yet synced
    synced_at = db.Column(db.DateTime, nullable=True)
    # start.gg internal event ID for the Melee singles event within this tournament
    startgg_event_id = db.Column(db.String(50), nullable=True)
    # Parry.gg identifiers for events discovered through the second provider.
    parrygg_id = db.Column(db.String(50), nullable=True)
    parrygg_slug = db.Column(db.String(200), nullable=True)
    parrygg_event_id = db.Column(db.String(50), nullable=True)
    # Soft-delete: excluded from standings, leaderboard, and future syncs
    removed = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    season = db.relationship("Season", back_populates="tournaments")
    entries = db.relationship("TournamentEntry", back_populates="tournament", cascade="all, delete-orphan")

    def to_dict(self):
        synced_at = self.synced_at
        if synced_at and synced_at.tzinfo is None:
            synced_at = synced_at.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "name": self.name,
            "date": self.date.isoformat() if self.date else None,
            "season_id": self.season_id,
            "startgg_id": self.startgg_id,
            "startgg_slug": self.startgg_slug,
            "parrygg_id": self.parrygg_id,
            "parrygg_slug": self.parrygg_slug,
            "parrygg_event_id": self.parrygg_event_id,
            "total_entrants": self.total_entrants,
            "synced_at": synced_at.isoformat().replace("+00:00", "Z") if synced_at else None,
            "removed": self.removed,
        }
