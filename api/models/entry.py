from api.extensions import db
from api.utils import calculate_spr, spr_to_points


class TournamentEntry(db.Model):
    __tablename__ = "tournament_entries"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False)
    seed = db.Column(db.Integer, nullable=True)
    placement = db.Column(db.Integer, nullable=True)
    # Derived from seed + placement via calculate_spr(); stored for fast querying
    spr = db.Column(db.Integer, nullable=True)
    # Derived from spr via spr_to_points(); stored for fast aggregation
    points = db.Column(db.Integer, nullable=False, default=1)

    player = db.relationship("Player", back_populates="entries")
    tournament = db.relationship("Tournament", back_populates="entries")

    def compute(self):
        """Recompute spr and points from seed, placement, and the tournament's total_entrants."""
        if self.seed is None or self.placement is None:
            return
        if self.tournament is None or self.tournament.total_entrants is None:
            return
        self.spr = calculate_spr(self.seed, self.placement, self.tournament.total_entrants)
        self.points = spr_to_points(self.spr)

    def to_dict(self):
        return {
            "id": self.id,
            "player_id": self.player_id,
            "player_name": self.player.display_name if self.player else None,
            "tournament_id": self.tournament_id,
            "tournament_name": self.tournament.name if self.tournament else None,
            "seed": self.seed,
            "placement": self.placement,
            "spr": self.spr,
            "points": self.points,
        }
