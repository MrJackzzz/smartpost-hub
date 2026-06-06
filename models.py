import os
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        return self.username


class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subdomain = db.Column(db.String(100), unique=True, nullable=False)
    instance_url = db.Column(db.String(500))
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'))
    status = db.Column(db.String(20), default='active')
    max_users = db.Column(db.Integer, default=5)
    notes = db.Column(db.Text)
    db_url = db.Column(db.String(500))
    last_heartbeat = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime)

    plan = db.relationship('Plan', backref='clients')
    stats = db.relationship('ClientStat', backref='client', lazy='dynamic')


class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, default=0)
    max_users = db.Column(db.Integer, default=5)
    max_products = db.Column(db.Integer, default=500)
    features = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)


class ClientStat(db.Model):
    __tablename__ = 'client_stats'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_sales = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0)
    total_products = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('client_id', 'date'),)


class System(db.Model):
    __tablename__ = 'systems'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    tagline = db.Column(db.String(300))
    description = db.Column(db.Text)
    logo_url = db.Column(db.String(500))
    price = db.Column(db.String(100))
    category = db.Column(db.String(100))
    demo_url = db.Column(db.String(500))
    features = db.Column(db.Text)
    videos = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
