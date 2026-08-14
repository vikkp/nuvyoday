"""Flask routes for Nuvyoday."""

from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from . import db
from .connection import decrypt_password, encrypt_password, test_connection
from .models import Connection

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    connections = Connection.query.order_by(Connection.name).all()
    return render_template("index.html", connections=connections)


@bp.route("/connections")
def connections_list():
    connections = Connection.query.order_by(Connection.name).all()
    return render_template("connections.html", connections=connections)


@bp.route("/connections/new", methods=["GET", "POST"])
def connection_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        host = request.form.get("host", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        port = request.form.get("port", "8473").strip() or "8473"
        use_ssl = request.form.get("use_ssl") == "on"
        libraries = request.form.get("libraries", "").strip()
        notes = request.form.get("notes", "").strip()

        if not all([name, host, username, password]):
            flash("Name, Host, Username and Password are required.", "danger")
            return render_template("connection_form.html", connection=None)

        try:
            port_int = int(port)
        except ValueError:
            flash("Port must be a number.", "danger")
            return render_template("connection_form.html", connection=None)

        conn = Connection(
            name=name,
            host=host,
            port=port_int,
            username=username,
            password_encrypted=encrypt_password(password),
            use_ssl=use_ssl,
            libraries=libraries,
            notes=notes,
        )
        db.session.add(conn)
        try:
            db.session.commit()
            flash(f"Connection “{name}” created successfully.", "success")
            return redirect(url_for("main.connections_list"))
        except IntegrityError:
            db.session.rollback()
            flash("A connection with that name already exists.", "danger")

    return render_template("connection_form.html", connection=None)


@bp.route("/connections/<int:conn_id>/edit", methods=["GET", "POST"])
def connection_edit(conn_id):
    conn = Connection.query.get_or_404(conn_id)

    if request.method == "POST":
        conn.name = request.form.get("name", "").strip()
        conn.host = request.form.get("host", "").strip()
        conn.username = request.form.get("username", "").strip()
        port = request.form.get("port", "8473").strip() or "8473"
        conn.use_ssl = request.form.get("use_ssl") == "on"
        conn.libraries = request.form.get("libraries", "").strip()
        conn.notes = request.form.get("notes", "").strip()

        new_password = request.form.get("password", "")
        if new_password:
            conn.password_encrypted = encrypt_password(new_password)

        try:
            conn.port = int(port)
        except ValueError:
            flash("Port must be a number.", "danger")
            return render_template("connection_form.html", connection=conn)

        db.session.commit()
        flash(f"Connection “{conn.name}” updated.", "success")
        return redirect(url_for("main.connections_list"))

    return render_template("connection_form.html", connection=conn)


@bp.route("/connections/<int:conn_id>/test", methods=["POST"])
def connection_test(conn_id):
    conn = Connection.query.get_or_404(conn_id)
    try:
        password = decrypt_password(conn.password_encrypted)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("main.connections_list"))

    success, message = test_connection(
        host=conn.host,
        username=conn.username,
        password=password,
        port=conn.port,
        use_ssl=conn.use_ssl,
    )

    conn.last_tested_at = datetime.now(timezone.utc)
    conn.last_test_success = success
    conn.last_test_message = message
    db.session.commit()

    if success:
        flash(f"✅ {conn.name}: {message}", "success")
    else:
        flash(f"❌ {conn.name}: {message}", "danger")

    return redirect(url_for("main.connections_list"))


@bp.route("/connections/<int:conn_id>/delete", methods=["POST"])
def connection_delete(conn_id):
    conn = Connection.query.get_or_404(conn_id)
    name = conn.name
    db.session.delete(conn)
    db.session.commit()
    flash(f"Connection “{name}” deleted.", "info")
    return redirect(url_for("main.connections_list"))
