"""
JT400 (IBM Toolbox for Java) connection wrapper using JPype.

Requires:
  - Java 8+ installed and on PATH (or JAVA_HOME set)
  - jt400.jar (or jtopen-*.jar) placed in lib/ or path provided via config
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

# JPype is imported lazily so the rest of the app can start even if Java is missing
_jpype = None
_jvm_started = False
_jvm_lock = threading.Lock()


def _get_jpype():
    global _jpype
    if _jpype is None:
        import jpype
        import jpype.imports  # noqa: F401
        _jpype = jpype
    return _jpype


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a stable 32-byte key from the Flask secret for Fernet."""
    import base64
    import hashlib
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_password(plain: str) -> str:
    key = _derive_fernet_key(current_app.config["SECRET_KEY"])
    f = Fernet(key)
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_password(token: str) -> str:
    key = _derive_fernet_key(current_app.config["SECRET_KEY"])
    f = Fernet(key)
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Unable to decrypt password \u2013 SECRET_KEY may have changed")


def ensure_jvm(jar_path: Optional[str] = None) -> None:
    """Start the JVM once (thread-safe) and load JT400."""
    global _jvm_started
    with _jvm_lock:
        if _jvm_started:
            return

        jpype = _get_jpype()
        if jpype.isJVMStarted():
            _jvm_started = True
            return

        jar = jar_path or current_app.config.get("JT400_JAR")
        jar_path_obj = Path(jar) if jar else None

        if not jar_path_obj or not jar_path_obj.exists():
            raise FileNotFoundError(
                f"JT400 jar not found at '{jar}'. "
                "Download the latest jt400.jar / jtopen-*.jar from "
                "https://github.com/IBM/JTOpen/releases or Maven Central "
                "and place it in the lib/ folder."
            )

        jvmpath = None
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            candidate = Path(java_home) / "lib" / "server" / "libjvm.so"
            if not candidate.exists():
                for p in [
                    Path(java_home) / "bin" / "server" / "jvm.dll",
                    Path(java_home) / "lib" / "server" / "libjvm.dylib",
                ]:
                    if p.exists():
                        candidate = p
                        break
            if candidate.exists():
                jvmpath = str(candidate)

        classpath = str(jar_path_obj.resolve())
        args = [f"-Djava.class.path={classpath}"]

        if jvmpath:
            jpype.startJVM(jvmpath, *args, convertStrings=True)
        else:
            jpype.startJVM(*args, convertStrings=True)

        _jvm_started = True


class IBMiConnection:
    """High-level wrapper around a single AS400 connection."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 8473,
        use_ssl: bool = False,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self._system = None

    def connect(self) -> None:
        ensure_jvm()
        jpype = _get_jpype()

        from com.ibm.as400.access import AS400  # type: ignore

        self._system = AS400(self.host, self.username, self.password)
        if self.use_ssl:
            pass

        self._system.connectService(AS400.COMMAND)

    def disconnect(self) -> None:
        if self._system is not None:
            try:
                self._system.disconnectAllServices()
            except Exception:
                pass
            self._system = None

    def test(self) -> Tuple[bool, str]:
        """
        Try to connect and run a trivial command.
        Returns (success: bool, message: str)
        """
        try:
            self.connect()

            from com.ibm.as400.access import CommandCall  # type: ignore

            cmd = CommandCall(self._system)
            success = cmd.run("DSPSYSVAL SYSVAL(QMODEL) OUTPUT(*PRINT)")
            msg = "Connection successful"
            if not success:
                messages = cmd.getMessageList()
                if messages:
                    msg = f"Connected, but command returned: {messages[0].getText()}"
                else:
                    msg = "Connected (command had non-zero status but no message)"

            return True, msg
        except Exception as e:
            return False, str(e)
        finally:
            self.disconnect()

    def get_system_info(self) -> dict:
        """Return basic system information (future expansion)."""
        return {
            "host": self.host,
            "username": self.username,
        }

    # ------------------------------------------------------------------
    # Inventory helpers (ADR0002)
    # ------------------------------------------------------------------

    def list_libraries(self, preferred: list[str] | None = None) -> list[dict]:
        """
        Return a list of libraries visible to the connection user.
        If preferred is provided, only those libraries are returned (if they exist).
        """
        self.connect()
        try:
            from com.ibm.as400.access import ObjectList  # type: ignore

            results = []
            if preferred:
                for lib_name in preferred:
                    lib_name = lib_name.strip().upper()
                    if not lib_name:
                        continue
                    try:
                        ol = ObjectList(self._system, lib_name, "*LIB", "*ALL")
                        ol.load()
                        results.append({
                            "name": lib_name,
                            "text_description": "",
                        })
                    except Exception:
                        continue
            else:
                ol = ObjectList(self._system, "QSYS", "*LIB", "*ALL")
                ol.load()
                count = 0
                while ol.next() and count < 200:
                    obj = ol.getObject()
                    name = str(obj.getName()).strip().upper()
                    if name.startswith("Q") and name not in ("QGPL", "QTEMP"):
                        continue
                    results.append({
                        "name": name,
                        "text_description": str(obj.getTextDescription() or ""),
                    })
                    count += 1
            return results
        finally:
            self.disconnect()

    def list_source_files(self, library: str) -> list[dict]:
        """List source physical files (*FILE with attribute PF-SRC) in a library."""
        self.connect()
        try:
            from com.ibm.as400.access import ObjectList  # type: ignore

            library = library.strip().upper()
            results = []
            ol = ObjectList(self._system, library, "*FILE", "*ALL")
            ol.load()
            while ol.next():
                obj = ol.getObject()
                name = str(obj.getName()).strip().upper()
                if name.endswith("SRC") or name in (
                    "QCLSRC", "QRPGSRC", "QDDSSRC", "QPNLSRC", "QCBLSRC"
                ):
                    results.append({
                        "name": name,
                        "text_description": str(obj.getTextDescription() or ""),
                    })
            return results
        finally:
            self.disconnect()

    def list_members(self, library: str, source_file: str) -> list[dict]:
        """List members of a source physical file."""
        self.connect()
        try:
            from com.ibm.as400.access import MemberList  # type: ignore

            library = library.strip().upper()
            source_file = source_file.strip().upper()
            results = []

            ml = MemberList(self._system, library, source_file)
            ml.load()
            while ml.next():
                mbr = ml.getMember()
                name = str(mbr.getName()).strip().upper()
                src_type = str(mbr.getSourceType() or "").strip().upper()
                text = str(mbr.getTextDescription() or "")
                results.append({
                    "member": name,
                    "source_type": src_type,
                    "text_description": text,
                    "last_changed": None,
                })
            return results
        finally:
            self.disconnect()

    def get_member_source(self, library: str, source_file: str, member: str) -> str:
        """
        Retrieve the source text of a single member.
        Returns the source as a single string (lines joined by newlines).
        """
        self.connect()
        try:
            from com.ibm.as400.access import SequentialFile, QSYSObjectPathName  # type: ignore

            library = library.strip().upper()
            source_file = source_file.strip().upper()
            member = member.strip().upper()

            path = QSYSObjectPathName(library, source_file, member, "MBR")
            sf = SequentialFile(self._system, path.getPath())
            sf.setReadNoWrite()
            sf.open()
            try:
                lines = []
                record = sf.readNext()
                while record is not None:
                    text = str(record).rstrip()
                    lines.append(text)
                    record = sf.readNext()
                return "\n".join(lines)
            finally:
                sf.close()
        finally:
            self.disconnect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False


def test_connection(
    host: str,
    username: str,
    password: str,
    port: int = 8473,
    use_ssl: bool = False,
) -> Tuple[bool, str]:
    """Convenience function used by the web UI."""
    conn = IBMiConnection(host, username, password, port=port, use_ssl=use_ssl)
    return conn.test()
