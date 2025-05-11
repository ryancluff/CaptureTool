from argparse import ArgumentParser
import hashlib
import json
import numpy as np
from pathlib import Path
import wavio

from forge_cli.api import ForgeApi

FORGE_DIR = ".forge"


def _read_config(
    path: Path,
) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
    return config


def _init(api: str, overwrite: bool = False) -> Path:
    init_db = {
        "api": api,
        "cursor": {resource_type: None for resource_type in ForgeApi.Resource.TYPES},
    }

    forge_dir = Path(FORGE_DIR)
    forge_dir.mkdir(exist_ok=True)
    inputs_dir = Path(forge_dir, "inputs")
    inputs_dir.mkdir(exist_ok=True)
    captures_dir = Path(forge_dir, "captures")
    captures_dir.mkdir(exist_ok=True)

    db_path = Path(forge_dir, "db.json")
    if not db_path.exists() or overwrite:
        _write_db(init_db)
    return forge_dir


def _read_db() -> dict:
    with open(Path(FORGE_DIR, "db.json"), "r") as fp:
        db = json.load(fp)
    return db


def _write_db(db: dict) -> None:
    with open(Path(FORGE_DIR, "db.json"), "w") as fp:
        json.dump(db, fp, indent=4)


def _get_api() -> dict:
    db = _read_db()
    return db["api"]


def _get_cursor(resource_type: str) -> str:
    db = _read_db()
    if resource_type not in db["cursor"] or db["cursor"][resource_type] is None:
        raise ValueError(f"Resource {resource_type} not set")
    return db["cursor"][resource_type]


def _set_cursor(resource_type: str, resource_id: str) -> None:
    db = _read_db()
    db["cursor"][resource_type] = resource_id
    _write_db(db)


def cli():
    parser = ArgumentParser(description="forge cli")
    parser.add_argument("--api", type=str, default="http://localhost:8000")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the db if it exists")

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="list forge resources")
    list_parser.add_argument("resource_type", type=str, choices=ForgeApi.Resource.TYPES_PLURAL, help="resource type")

    create_parser = subparsers.add_parser("create", help="create a new forge resource")
    create_parser.add_argument("resource_type", type=str, choices=ForgeApi.Resource.TYPES, help="resource type")
    create_parser.add_argument("config_path", type=str, help="path to config file")

    get_parser = subparsers.add_parser("get", help="get a forge resource")
    get_parser.add_argument("resource_type", type=str, choices=ForgeApi.Resource.TYPES, help="resource type")
    get_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="resource id (or name)")

    delete_parser = subparsers.add_parser("delete", help="delete a forge resource")
    delete_parser.add_argument("resource_type", type=str, choices=ForgeApi.Resource.TYPES, help="resource type")
    delete_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="resource id (or name)")

    upload_parser = subparsers.add_parser("upload", help="upload a file")
    upload_parser.add_argument("resource_type", type=str, choices=ForgeApi.File.TYPES, help="resource type")
    upload_parser.add_argument("file_path", type=str, help="path to file")
    upload_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="resource id (or name)")

    download_parser = subparsers.add_parser("download", help="download a file")
    download_parser.add_argument("resource_type", type=str, choices=ForgeApi.File.TYPES, help="resource type")
    download_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="resource id (or name)")

    args = parser.parse_args()

    forge_dir = Path(FORGE_DIR)
    if not forge_dir.exists() or args.overwrite:
        _init(args.api, overwrite=args.overwrite)
    api = ForgeApi(_get_api())

    resource_type = args.resource_type

    if args.command in ["get", "delete", "upload", "download"]:
        if args.resource_id is not None:
            _set_cursor(resource_type, args.resource_id)
        resource_id = _get_cursor(resource_type)

        if args.command == "get":
            resource = api.get(resource_type, resource_id)
            _set_cursor(resource_type, resource_id)
            print(f"{resource_type}: {json.dumps(resource, indent=4)}")
        elif args.command == "delete":
            resource = api.delete(resource_type, resource_id)
            print(f"deleted {resource_type}: {json.dumps(resource, indent=4)}")
        elif args.command == "upload":
            with open(args.file_path, "rb") as fp:
                file_hash = hashlib.file_digest(fp, "sha256").hexdigest()
            config = {
                "hash": file_hash,
            }
            resource = api.update(resource_type, resource_id, config)
            resource = api.upload(resource_type, resource_id, args.file_path)
            print(f"uploaded {resource_type}: {json.dumps(resource, indent=4)}")
    else:
        if args.command == "list":
            resources = api.list(resource_type)
            print(f"{resource_type}: {json.dumps(resources, indent=4)}")
        elif args.command == "create":
            config = _read_config(args.config_path)
            if resource_type == "capture":
                config["input"] = _get_cursor("input")
                config["session"] = _get_cursor("session")
            elif resource_type == "snapshot":
                config["capture"] = _get_cursor("capture")
            resource = api.create(resource_type, config)
            _set_cursor(resource_type, resource_id)
            print(f"created {resource_type}: {json.dumps(resource, indent=4)}")


if __name__ == "__main__":
    cli()
