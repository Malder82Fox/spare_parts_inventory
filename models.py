from datetime import datetime
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # user, admin, root

    def __repr__(self):
        return f'<User {self.username}>'

class Part(db.Model):
    __tablename__ = 'parts'
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

    def __repr__(self):
        return f'<Part {self.sap_code}: {self.name}>'
