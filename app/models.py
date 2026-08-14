"""SQLAlchemy models for Nuvyoday."""

from datetime import datetime, timezone

from . import db


def utcnow():
    return datetime.now(timezone.utc)


class Connection(db.Model):
    """Stored IBM i connection profile."""

    __tablename__ = "connections"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=8473)  # default non-SSL host server port
    username = db.Column(db.String(64), nullable=False)
    password_encrypted = db.Column(db.Text, nullable=False)
    use_ssl = db.Column(db.Boolean, default=False)
    libraries = db.Column(db.Text, default="")  # comma-separated preferred libraries
    notes = db.Column(db.Text, default="")
    last_tested_at = db.Column(db.DateTime, nullable=True)
    last_test_success = db.Column(db.Boolean, nullable=True)
    last_test_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<Connection {self.name} ({self.host})>"


class SourceMember(db.Model):
    """Placeholder for future source inventory."""

    __tablename__ = "source_members"

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("connections.id"), nullable=False)
    library = db.Column(db.String(10), nullable=False)
    source_file = db.Column(db.String(10), nullable=False)  # e.g. QCLSRC
    member = db.Column(db.String(10), nullable=False)
    source_type = db.Column(db.String(10), default="")  # CLP, RPGLE, DSPF, etc.
    text_description = db.Column(db.String(50), default="")
    last_changed = db.Column(db.DateTime, nullable=True)
    source_content = db.Column(db.Text, nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    connection = db.relationship("Connection", backref=db.backref("members", lazy=True))

    def __repr__(self):
        return f"<SourceMember {self.library}/{self.source_file}({self.member})>"
