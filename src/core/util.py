from datetime import datetime
import hashlib
import json
from pathlib import Path


def read_config(
    path: Path,
) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
    return config


def write_config(
    capture_dir: Path,
    config: dict,
    name: str = "config",
) -> None:
    with open(Path(capture_dir, name + ".json"), "w") as fp:
        json.dump(config, fp, indent=4)


def timestamp() -> str:
    t = datetime.now()
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}-{t.hour:02d}-{t.minute:02d}-{t.second:02d}"


def hash(path: Path) -> str:
    with open(path, "rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return digest.hexdigest()
