from api.extensions import db


class Season(db.Model):
    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    # draft | active | completed
    status = db.Column(db.String(20), nullable=False, default="draft")
    # Date range used for start.gg sync — can differ from season start/end
    # e.g. sync_from may be a week before season starts to catch early tournaments
    sync_from = db.Column(db.Date, nullable=True)
    sync_to = db.Column(db.Date, nullable=True)

    teams = db.relationship("Team", back_populates="season", cascade="all, delete-orphan")
    tournaments = db.relationship("Tournament", back_populates="season", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "sync_from": self.sync_from.isoformat() if self.sync_from else None,
            "sync_to": self.sync_to.isoformat() if self.sync_to else None,
        }
