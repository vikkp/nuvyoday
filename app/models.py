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
    port = db.Column(db.Integer, default=8473)
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

    def preferred_libraries_list(self):
        if not self.libraries:
            return []
        return [lib.strip().upper() for lib in self.libraries.split(",") if lib.strip()]

    def __repr__(self):
        return f"<Connection {self.name} ({self.host})>"


class Library(db.Model):
    """Discovered library for a connection (inventory)."""

    __tablename__ = "libraries"

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("connections.id"), nullable=False)
    name = db.Column(db.String(10), nullable=False)
    text_description = db.Column(db.String(50), default="")
    discovered_at = db.Column(db.DateTime, default=utcnow)

    connection = db.relationship("Connection", backref=db.backref("discovered_libraries", lazy=True))

    __table_args__ = (
        db.UniqueConstraint("connection_id", "name", name="uq_library_conn_name"),
    )

    def __repr__(self):
        return f"<Library {self.name}>"


class SourceFile(db.Model):
    """Source physical file (*FILE PF-SRC) inside a library."""

    __tablename__ = "source_files"

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("connections.id"), nullable=False)
    library = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(10), nullable=False)  # e.g. QCLSRC, QRPGSRC
    text_description = db.Column(db.String(50), default="")
    discovered_at = db.Column(db.DateTime, default=utcnow)

    connection = db.relationship("Connection", backref=db.backref("source_files", lazy=True))

    __table_args__ = (
        db.UniqueConstraint("connection_id", "library", "name", name="uq_srcfile_conn_lib_name"),
    )

    def __repr__(self):
        return f"<SourceFile {self.library}/{self.name}>"


class SourceMember(db.Model):
    """Individual source member + optional harvested content."""

    __tablename__ = "source_members"

    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("connections.id"), nullable=False)
    library = db.Column(db.String(10), nullable=False)
    source_file = db.Column(db.String(10), nullable=False)
    member = db.Column(db.String(10), nullable=False)
    source_type = db.Column(db.String(10), default="")  # CLP, RPGLE, DSPF, etc.
    text_description = db.Column(db.String(50), default="")
    last_changed = db.Column(db.DateTime, nullable=True)
    source_content = db.Column(db.Text, nullable=True)
    content_hash = db.Column(db.String(64), nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    connection = db.relationship("Connection", backref=db.backref("members", lazy=True))

    __table_args__ = (
        db.UniqueConstraint(
            "connection_id", "library", "source_file", "member",
            name="uq_member_conn_lib_file_mbr"
        ),
    )

    @property
    def is_harvested(self):
        return self.source_content is not None and self.fetched_at is not None

    def __repr__(self):
        return f"<SourceMember {self.library}/{self.source_file}({self.member})>"
