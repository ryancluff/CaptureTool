import json
from pathlib import Path

from forge_cli.api import ForgeApi
from capture_tool.interface import AudioInterface


class ForgeDB:
    FORGE_DIR = ".forge"

    INIT_DB = {
        "api": None,
        "cursor": {resource_type: None for resource_type in ForgeApi.Resource.TYPES},
        "interface": AudioInterface.INIT_SETTINGS,
    }

    @classmethod
    def _read_db(cls) -> dict:
        with open(Path(cls.FORGE_DIR, "db.json"), "r") as fp:
            db = json.load(fp)
        return db

    @classmethod
    def _write_db(cls, db: dict) -> None:
        with open(Path(cls.FORGE_DIR, "db.json"), "w") as fp:
            json.dump(db, fp, indent=4)

    def __init__(self, api: str = None, overwrite: bool = False) -> Path:
        forge_dir = Path(self.FORGE_DIR)
        forge_dir.mkdir(exist_ok=True)
        inputs_dir = Path(forge_dir, "inputs")
        inputs_dir.mkdir(exist_ok=True)
        captures_dir = Path(forge_dir, "captures")
        captures_dir.mkdir(exist_ok=True)

        db_path = Path(forge_dir, "db.json")
        if not db_path.exists() or overwrite:
            init_db = self.INIT_DB
            init_db["api"] = api
            self._write_db(init_db)
        return forge_dir

    def get_api(self) -> dict:
        db = self._read_db()
        return db["api"]

    def get_cursor(self, resource_type: str) -> str:
        db = self._read_db()
        if resource_type not in db["cursor"] or db["cursor"][resource_type] is None:
            raise ValueError(f"Resource {resource_type} not set")
        return db["cursor"][resource_type]

    def set_cursor(self, resource_type: str, resource_id: str) -> None:
        db = self._read_db()
        db["cursor"][resource_type] = resource_id
        self._write_db(db)
