"""Writable user data stays separate from immutable application resources."""
import os
from pathlib import Path
import sys


def default_db_path():
    override = os.environ.get('WEBSHEET_DB')
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        fallback = Path.home() / 'AppData' / 'Local'
        root = Path(os.environ.get('LOCALAPPDATA') or fallback)
        if not root.is_absolute():
            root = fallback
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library' / 'Application Support'
    else:
        fallback = Path.home() / '.local' / 'share'
        root = Path(os.environ.get('XDG_DATA_HOME') or fallback)
        if not root.is_absolute():
            root = fallback
    return root / 'WebSheetAgent' / 'websheet.sqlite3'
