from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

post_tags = db.Table(
    'post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    posts = db.relationship('Post', backref='category', lazy=True)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    body = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(300))
    meta_description = db.Column(db.String(300))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    tags = db.relationship('Tag', secondary=post_tags, backref='posts')
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    view_count = db.Column(db.Integer, default=0)


class AffiliateLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    link_type = db.Column(db.String(20), nullable=False)
    placement = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(300))
    active = db.Column(db.Boolean, default=True)
    height = db.Column(db.Integer, default=500)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ClickLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    affiliate_link_id = db.Column(db.Integer, db.ForeignKey('affiliate_link.id'), nullable=False)
    post_slug = db.Column(db.String(200))
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    affiliate_link = db.relationship('AffiliateLink', backref='clicks')


class Tip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    page = db.Column(db.String(50), default='flights')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)