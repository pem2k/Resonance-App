from api.extensions import db


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(100), nullable=False)
    # start.gg identifiers — nullable until linked
    startgg_id = db.Column(db.String(50), nullable=True, unique=True)
    startgg_slug = db.Column(db.String(100), nullable=True)
    # Parry.gg profile UUID — nullable until linked.
    parrygg_id = db.Column(db.String(50), nullable=True)

    entries = db.relationship("TournamentEntry", back_populates="player", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "display_name": self.display_name,
            "startgg_id": self.startgg_id,
            "startgg_slug": self.startgg_slug,
            "parrygg_id": self.parrygg_id,
        }
