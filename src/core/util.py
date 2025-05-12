import json
from pathlib import Path


def read_config(
    path: Path,
) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
    return config
