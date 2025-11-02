"""SQLAlchemy models for the spare parts domain."""

from datetime import datetime

from extensions import db


class Part(db.Model):
    """Represents a spare part item."""

    __tablename__ = "parts"

    id = db.Column(db.Integer, primary_key=True)
    sap_code = db.Column(db.String(50), unique=True, nullable=False)
    part_number = db.Column(db.String(100))
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    equipment_code = db.Column(db.String(50))
    location = db.Column(db.String(50))
    manufacturer = db.Column(db.String(100))
    analog_group = db.Column(db.String(50))
    photo_path = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Part {self.sap_code}: {self.name}>"
