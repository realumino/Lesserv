"""Fill the Xray config from the database, write it, and run Xray.

Why this exists: it is the only module that touches the filesystem and the
Xray subprocess. Everything upstream (user_service, main) just calls
sync(); everything downstream (config_service, allocator) stays pure and
testable.

Design rules kept here on purpose:
- Nothing ever raises: a missing template or binary is an expected state
  on a fresh install, so every step logs a warning and gives up.
- The process handle is module-level (not app.state) because user_service
  has no access to the app object.
- stop/start hold a lock because sync() runs in FastAPI's worker threads.
"""

import json
import logging
import os
import shutil
import subprocess
import threading

from backend import db, settings
from backend.services import config_service

logger = logging.getLogger(__name__)

_process = None
_lock = threading.Lock()


def load_template():
    """Read the user-provided template; return None when missing or invalid.

    Why None instead of raising: "no template yet" is a normal fresh-install
    state — the panel must keep serving users while waiting for the admin
    to drop the file in (or POST one in milestone 3).
    """
    path = settings.TEMPLATE_PATH
    if not os.path.exists(path):
        logger.warning("template not found at %s; skipping sync", path)
        return None
    with open(path, encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            logger.warning("template at %s is not valid JSON; skipping sync", path)
            return None


def save_template(content):
    """Atomically write a new template to the template path.

    Why this exists: POST /api/config needs a counterpart to load_template().
    A temp file + os.replace keeps the write atomic so nothing reads a
    half-written file. The caller is responsible for supplying valid JSON
    — the template is opaque; we never validate its structure.
    """
    path = settings.TEMPLATE_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(content, handle, indent=2)
    os.replace(tmp_path, path)


def write_config(config):
    """Atomically write the filled config to the path Xray will read.

    Why temp file + os.replace: writing in place could hand Xray a
    half-written file on a crash; the replace is atomic on the same disk.
    """
    path = settings.XRAY_CONFIG_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    os.replace(tmp_path, path)


def _binary_available():
    """Return True when the Xray binary actually exists on this machine.

    Why both checks: the default "xray" must be found via PATH, but
    settings may also point at an absolute path that is simply not there.
    """
    binary = settings.XRAY_BINARY
    return shutil.which(binary) is not None or os.path.exists(binary)


def start():
    """Launch the Xray subprocess with the generated config; no-op in dev.

    Why stdout/stderr are inherited: Xray's own log is the operator's
    debugging window; nothing else in the panel parses it.

    Why the 2-second early-exit check: Xray dies within moments when the
    config is invalid; without this the panel would believe it is running
    when it is not.
    """
    global _process
    with _lock:
        if _process is not None and _process.poll() is None:
            logger.warning("Xray already running (pid %s); not starting again",
                           _process.pid)
            return
        if not _binary_available():
            logger.warning("Xray binary %r not found; skipping start (dev?)",
                           settings.XRAY_BINARY)
            return
        _process = subprocess.Popen(
            [settings.XRAY_BINARY, "run", "-config", settings.XRAY_CONFIG_PATH]
        )
        try:
            _process.wait(timeout=2)
            logger.error("Xray exited immediately with code %s; check %s",
                         _process.returncode, settings.XRAY_CONFIG_PATH)
            _process = None
        except subprocess.TimeoutExpired:
            logger.info("started Xray pid %s", _process.pid)


def stop():
    """Terminate the Xray subprocess; no-op when it is not running.

    Why terminate + wait: terminate asks politely; wait gives it a moment
    before kill. A zombie would hold the port and break the next start.
    """
    global _process
    with _lock:
        if _process is None or _process.poll() is not None:
            _process = None
            return
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Xray did not exit within 5s; killing it")
            _process.kill()
        _process = None


def restart():
    """Stop then start, so a regenerated config becomes live.

    Why this exists: Xray reads its config only at startup, so every sync
    that rewrites the file must bounce the process. (No gRPC API in v1.)
    """
    stop()
    start()


def status():
    """Return the Xray subprocess health: whether it is running and its pid.

    Why this exists: GET /api/status needs a simple snapshot of the process
    without touching the lock or triggering side effects. A read of the
    module-level reference is atomic in CPython.
    """
    global _process
    proc = _process
    if proc is not None and proc.poll() is None:
        return {"running": True, "pid": proc.pid}
    return {"running": False, "pid": None}


def sync(conn):
    """Regenerate the Xray config from the database and restart Xray.

    Why one entry point: user_service calls exactly this after every user
    change and main calls it once at startup. Malformed templates raise
    KeyError/TypeError here, which are logged as warnings — a user edit
    must never take the API down.
    """
    template = load_template()
    if template is None:
        return
    users = db.list_users(conn)
    try:
        config, warnings = config_service.build_config(template, users)
    except (KeyError, TypeError) as error:
        logger.warning("template looks malformed (%s); skipping sync", error)
        return
    for warning in warnings:
        logger.warning("sync: %s", warning)
    write_config(config)
    restart()
