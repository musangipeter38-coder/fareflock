from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class AffiliateLink(db.Model):
    __tablename__ = 'affiliate_link'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    link_type = db.Column(db.String(20), default='url')
    placement = db.Column(db.String(50), nullable=True)
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    height = db.Column(db.Integer, default=500)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ClickLog(db.Model):
    __tablename__ = 'click_log'
    id = db.Column(db.Integer, primary_key=True)
    affiliate_link_id = db.Column(db.Integer, db.ForeignKey('affiliate_link.id'), nullable=True)
    post_slug = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WhatsAppTracker(db.Model):
    __tablename__ = 'whatsapp_tracker'
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(30), nullable=False)
    origin = db.Column(db.String(10), nullable=False)
    destination = db.Column(db.String(10), nullable=False)
    target_price = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)