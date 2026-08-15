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
            flash(f"Connection \u201c{name}\u201d created successfully.", "success")
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
        flash(f"Connection \u201c{conn.name}\u201d updated.", "success")
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
        flash(f"\u2705 {conn.name}: {message}", "success")
    else:
        flash(f"\u274c {conn.name}: {message}", "danger")

    return redirect(url_for("main.connections_list"))


@bp.route("/connections/<int:conn_id>/delete", methods=["POST"])
def connection_delete(conn_id):
    conn = Connection.query.get_or_404(conn_id)
    name = conn.name
    db.session.delete(conn)
    db.session.commit()
    flash(f"Connection \u201c{name}\u201d deleted.", "info")
    return redirect(url_for("main.connections_list"))


# ---------------------------------------------------------------------------
# Inventory & Harvesting (ADR0002)
# ---------------------------------------------------------------------------

from .connection import IBMiConnection
from .models import Library, SourceFile, SourceMember
import hashlib


def _get_live_connection(conn: Connection) -> IBMiConnection:
    password = decrypt_password(conn.password_encrypted)
    return IBMiConnection(
        host=conn.host,
        username=conn.username,
        password=password,
        port=conn.port,
        use_ssl=conn.use_ssl,
    )


@bp.route("/inventory/<int:conn_id>")
def inventory(conn_id):
    """Show discovered libraries for a connection (or trigger discovery)."""
    conn = Connection.query.get_or_404(conn_id)
    libraries = Library.query.filter_by(connection_id=conn.id).order_by(Library.name).all()
    return render_template("inventory.html", connection=conn, libraries=libraries)


@bp.route("/inventory/<int:conn_id>/discover", methods=["POST"])
def inventory_discover(conn_id):
    """Run library discovery and store results."""
    conn = Connection.query.get_or_404(conn_id)
    preferred = conn.preferred_libraries_list()

    try:
        live = _get_live_connection(conn)
        discovered = live.list_libraries(preferred=preferred if preferred else None)
    except Exception as e:
        flash(f"Discovery failed: {e}", "danger")
        return redirect(url_for("main.inventory", conn_id=conn.id))

    existing = {lib.name: lib for lib in Library.query.filter_by(connection_id=conn.id).all()}
    added = 0
    for item in discovered:
        name = item["name"]
        if name not in existing:
            db.session.add(Library(
                connection_id=conn.id,
                name=name,
                text_description=item.get("text_description", "")[:50],
            ))
            added += 1
        else:
            existing[name].text_description = item.get("text_description", "")[:50]
    db.session.commit()
    flash(f"Discovery complete. {added} new libraries added, {len(discovered)} total visible.", "success")
    return redirect(url_for("main.inventory", conn_id=conn.id))


@bp.route("/inventory/<int:conn_id>/library/<library>")
def inventory_library(conn_id, library):
    """Show source files in a library."""
    conn = Connection.query.get_or_404(conn_id)
    library = library.upper()
    source_files = (
        SourceFile.query
        .filter_by(connection_id=conn.id, library=library)
        .order_by(SourceFile.name)
        .all()
    )
    return render_template(
        "inventory_library.html",
        connection=conn,
        library=library,
        source_files=source_files,
    )


@bp.route("/inventory/<int:conn_id>/library/<library>/discover", methods=["POST"])
def inventory_library_discover(conn_id, library):
    """Discover source physical files in a library."""
    conn = Connection.query.get_or_404(conn_id)
    library = library.upper()

    try:
        live = _get_live_connection(conn)
        discovered = live.list_source_files(library)
    except Exception as e:
        flash(f"Source file discovery failed: {e}", "danger")
        return redirect(url_for("main.inventory_library", conn_id=conn.id, library=library))

    existing = {
        sf.name: sf
        for sf in SourceFile.query.filter_by(connection_id=conn.id, library=library).all()
    }
    added = 0
    for item in discovered:
        name = item["name"]
        if name not in existing:
            db.session.add(SourceFile(
                connection_id=conn.id,
                library=library,
                name=name,
                text_description=item.get("text_description", "")[:50],
            ))
            added += 1
    db.session.commit()
    flash(f"Found {len(discovered)} source files ({added} new).", "success")
    return redirect(url_for("main.inventory_library", conn_id=conn.id, library=library))


@bp.route("/inventory/<int:conn_id>/library/<library>/<source_file>")
def inventory_members(conn_id, library, source_file):
    """Show members of a source file."""
    conn = Connection.query.get_or_404(conn_id)
    library = library.upper()
    source_file = source_file.upper()
    members = (
        SourceMember.query
        .filter_by(connection_id=conn.id, library=library, source_file=source_file)
        .order_by(SourceMember.member)
        .all()
    )
    return render_template(
        "inventory_members.html",
        connection=conn,
        library=library,
        source_file=source_file,
        members=members,
    )


@bp.route("/inventory/<int:conn_id>/library/<library>/<source_file>/discover", methods=["POST"])
def inventory_members_discover(conn_id, library, source_file):
    """Discover members of a source file (metadata only)."""
    conn = Connection.query.get_or_404(conn_id)
    library = library.upper()
    source_file = source_file.upper()

    try:
        live = _get_live_connection(conn)
        discovered = live.list_members(library, source_file)
    except Exception as e:
        flash(f"Member discovery failed: {e}", "danger")
        return redirect(url_for(
            "main.inventory_members",
            conn_id=conn.id, library=library, source_file=source_file
        ))

    existing = {
        m.member: m
        for m in SourceMember.query.filter_by(
            connection_id=conn.id, library=library, source_file=source_file
        ).all()
    }
    added = 0
    for item in discovered:
        name = item["member"]
        if name not in existing:
            db.session.add(SourceMember(
                connection_id=conn.id,
                library=library,
                source_file=source_file,
                member=name,
                source_type=item.get("source_type", "")[:10],
                text_description=item.get("text_description", "")[:50],
            ))
            added += 1
        else:
            existing[name].source_type = item.get("source_type", "")[:10]
            existing[name].text_description = item.get("text_description", "")[:50]
    db.session.commit()
    flash(f"Found {len(discovered)} members ({added} new).", "success")
    return redirect(url_for(
        "main.inventory_members",
        conn_id=conn.id, library=library, source_file=source_file
    ))


@bp.route("/inventory/<int:conn_id>/library/<library>/<source_file>/<member>/harvest", methods=["POST"])
def harvest_member(conn_id, library, source_file, member):
    """Pull the source text of a single member into SQLite."""
    conn = Connection.query.get_or_404(conn_id)
    library = library.upper()
    source_file = source_file.upper()
    member = member.upper()

    mbr = SourceMember.query.filter_by(
        connection_id=conn.id,
        library=library,
        source_file=source_file,
        member=member,
    ).first()
    if not mbr:
        flash("Member not found in inventory. Run discovery first.", "warning")
        return redirect(url_for(
            "main.inventory_members",
            conn_id=conn.id, library=library, source_file=source_file
        ))

    try:
        live = _get_live_connection(conn)
        content = live.get_member_source(library, source_file, member)
    except Exception as e:
        flash(f"Harvest failed: {e}", "danger")
        return redirect(url_for(
            "main.inventory_members",
            conn_id=conn.id, library=library, source_file=source_file
        ))

    mbr.source_content = content
    mbr.content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    mbr.fetched_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f"Harvested {library}/{source_file}({member}) \u2014 {len(content)} characters.", "success")
    return redirect(url_for(
        "main.inventory_members",
        conn_id=conn.id, library=library, source_file=source_file
    ))
