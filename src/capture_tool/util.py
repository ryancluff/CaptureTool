from datetime import datetime
import hashlib
from pathlib import Path


def timestamp() -> str:
    t = datetime.now()
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}-{t.hour:02d}-{t.minute:02d}-{t.second:02d}"


def hash(path: Path) -> str:
    with open(path, "rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return digest.hexdigest()
