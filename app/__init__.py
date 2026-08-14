"""Nuvyoday Flask application factory."""

import os
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Paths
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)

    # Configuration
    secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me-in-production")
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{data_dir / 'nuvyoday.db'}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JT400_JAR=os.getenv("JT400_JAR_PATH", str(base_dir / "lib" / "jt400.jar")),
    )

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)

    from . import models  # noqa: F401
    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app
