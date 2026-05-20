from api.extensions import db

# Association table — players on a team's roster
team_roster = db.Table(
    "team_roster",
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
    db.Column("player_id", db.Integer, db.ForeignKey("players.id"), primary_key=True),
)


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    # Captain is also in the roster; this is just a convenience FK
    captain_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)

    season = db.relationship("Season", back_populates="teams")
    captain = db.relationship("Player", foreign_keys=[captain_id])
    roster = db.relationship("Player", secondary=team_roster, backref="teams")

    def to_dict(self, include_roster=False):
        data = {
            "id": self.id,
            "name": self.name,
            "season_id": self.season_id,
            "captain": self.captain.to_dict() if self.captain else None,
        }
        if include_roster:
            data["roster"] = [p.to_dict() for p in self.roster]
        return data
