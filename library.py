"""
library.py — File-attachment store for Chronosophy.

Portraits and work files are copied into a ``library/`` folder that sits next to
``philosophers.db``.  The database stores only *relative* paths into this
folder, so the entire application directory can be moved or backed up and the
links still resolve.

Layout::

    library/
        portraits/<uuid>.<ext>
        works/<uuid>/<original filename>

Each work file lives in its own ``<uuid>`` sub-folder so the original filename
can be preserved verbatim (nice display, correct extension for the OS "open"
handler) without any chance of two files colliding.

This module is deliberately free of PyQt and database imports: it deals purely
with the filesystem, so the data layer can use it without pulling in the GUI
toolkit.
"""

import os
import re
import shutil
import uuid
from typing import Optional

# library/ sits next to this file (same directory as philosophers.db)
LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")
PORTRAITS_SUBDIR = "portraits"
WORKS_SUBDIR = "works"

# Characters we allow through verbatim in a stored filename. Anything else is
# replaced with "_" so a malicious or awkward name can never escape the folder
# or upset the filesystem.
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._ ()\-]+")


# ─── Path helpers ────────────────────────────────────────────────────────────

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _rel(*parts: str) -> str:
    """Build a relative path using forward slashes for cross-platform storage."""
    return "/".join(parts)


def abs_path(rel: Optional[str]) -> Optional[str]:
    """Resolve a stored relative path to an absolute one. Empty/None → None."""
    if not rel:
        return None
    return os.path.join(LIBRARY_DIR, rel.replace("/", os.sep))


def exists(rel: Optional[str]) -> bool:
    """True if the relative path points at a real file on disk."""
    p = abs_path(rel)
    return bool(p and os.path.isfile(p))


def sanitize_filename(name: str) -> str:
    """Reduce an arbitrary filename to a safe basename (no directories)."""
    name = os.path.basename(name or "").strip()
    name = _SAFE_CHARS.sub("_", name)
    name = name.strip(". ")          # never leading/trailing dots or spaces
    return name or "file"


# ─── Writing ─────────────────────────────────────────────────────────────────

def save_portrait_bytes(data: bytes, ext: str) -> str:
    """Write already-normalised portrait bytes into the store. Returns rel path."""
    ext = (ext or "png").lstrip(".").lower()
    _ensure_dir(os.path.join(LIBRARY_DIR, PORTRAITS_SUBDIR))
    rel = _rel(PORTRAITS_SUBDIR, f"{uuid.uuid4().hex}.{ext}")
    with open(abs_path(rel), "wb") as f:
        f.write(data)
    return rel


def import_work_file(source_path: str) -> tuple[str, str]:
    """Copy an external file into the works store.

    Returns ``(rel_path, original_filename)``.  The bytes are copied (not moved),
    so the user's original file is left untouched and can be deleted afterwards.
    """
    original = os.path.basename(source_path)
    safe = sanitize_filename(original)
    subdir = uuid.uuid4().hex
    dest_dir = os.path.join(LIBRARY_DIR, WORKS_SUBDIR, subdir)
    _ensure_dir(dest_dir)
    shutil.copy2(source_path, os.path.join(dest_dir, safe))
    return _rel(WORKS_SUBDIR, subdir, safe), original


def save_work_bytes(data: bytes, original_filename: str) -> tuple[str, str]:
    """Write provided bytes as a work file (used when restoring a backup).

    Returns ``(rel_path, original_filename)``.
    """
    safe = sanitize_filename(original_filename)
    subdir = uuid.uuid4().hex
    dest_dir = os.path.join(LIBRARY_DIR, WORKS_SUBDIR, subdir)
    _ensure_dir(dest_dir)
    with open(os.path.join(dest_dir, safe), "wb") as f:
        f.write(data)
    return _rel(WORKS_SUBDIR, subdir, safe), original_filename


# ─── Reading / deleting ──────────────────────────────────────────────────────

def read_bytes(rel: Optional[str]) -> Optional[bytes]:
    """Return the file's bytes, or None if the relative path has no real file."""
    p = abs_path(rel)
    if not p or not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return f.read()


def delete(rel: Optional[str]) -> None:
    """Delete a stored file (best-effort), tidying an emptied works sub-folder."""
    p = abs_path(rel)
    if not p:
        return
    try:
        if os.path.isfile(p):
            os.remove(p)
        # A works file lives in library/works/<uuid>/; remove that wrapper dir
        # once it is empty so the store does not accumulate stragglers.
        parent = os.path.dirname(p)
        roots = {
            os.path.normpath(os.path.join(LIBRARY_DIR, WORKS_SUBDIR)),
            os.path.normpath(os.path.join(LIBRARY_DIR, PORTRAITS_SUBDIR)),
            os.path.normpath(LIBRARY_DIR),
        }
        if (os.path.normpath(parent) not in roots
                and os.path.isdir(parent) and not os.listdir(parent)):
            os.rmdir(parent)
    except OSError:
        pass


def clear_all() -> None:
    """Remove every stored portrait and work file.

    Used by the full-replace import so a restored backup does not leave the
    previous database's attachments orphaned on disk.
    """
    for sub in (PORTRAITS_SUBDIR, WORKS_SUBDIR):
        d = os.path.join(LIBRARY_DIR, sub)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
