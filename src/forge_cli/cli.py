from argparse import ArgumentParser
import hashlib
from pathlib import Path
import json

from core.db import ForgeDB
from core.util import read_config, write_config
from forge_cli.api import ForgeApi


def _create_manifest(capture: dict, session: dict) -> None:
    capture_dir = Path(ForgeDB.FORGE_DIR, "captures", str(capture["id"]))
    capture_dir.mkdir(exist_ok=True)

    manifest = dict()
    manifest["capture_id"] = capture["id"]
    manifest["session_id"] = session["id"]
    manifest["input_id"] = capture["input"]

    manifest["parameters"] = dict()
    for i in range(len(session["parameter_labels"])):
        manifest["parameters"][session["parameter_labels"][i]] = capture["parameters"][i]
    manifest["switches"] = dict()
    for i in range(len(session["switch_labels"])):
        manifest["switches"][session["switch_labels"][i]] = capture["switches"][i]

    manifest["channels"] = session["channels"]
    manifest["level_dbu"] = capture["level_dbu"]

    write_config(capture_dir, manifest, "manifest")


def _setup_parser() -> ArgumentParser:
    parser = ArgumentParser(description="forge cli")
    parser.add_argument("--api", type=str, required=False)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the db if it exists",
    )
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="list forge resources")
    list_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.Resource.TYPES_PLURAL,
        help="resource type",
    )

    create_parser = subparsers.add_parser("create", help="create a new forge resource")
    create_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.Resource.TYPES,
        help="resource type",
    )
    create_parser.add_argument(
        "config_path",
        type=str,
        help="path to config file",
    )

    get_parser = subparsers.add_parser("get", help="get a forge resource")
    get_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.Resource.TYPES,
        help="resource type",
    )
    get_parser.add_argument(
        "resource_id",
        type=str,
        nargs="?",
        default=None,
        help="resource id (or name)",
    )

    delete_parser = subparsers.add_parser("delete", help="delete a forge resource")
    delete_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.Resource.TYPES,
        help="resource type",
    )
    delete_parser.add_argument(
        "resource_id",
        type=str,
        nargs="?",
        default=None,
        help="resource id (or name)",
    )

    upload_parser = subparsers.add_parser("upload", help="upload a file")
    upload_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.File.TYPES,
        help="resource type",
    )
    upload_parser.add_argument(
        "file_path",
        type=str,
        help="path to file",
    )
    upload_parser.add_argument(
        "resource_id",
        type=str,
        nargs="?",
        default=None,
        help="resource id (or name)",
    )

    download_parser = subparsers.add_parser("download", help="download a file")
    download_parser.add_argument(
        "resource_type",
        type=str,
        choices=ForgeApi.File.TYPES,
        help="resource type",
    )
    download_parser.add_argument(
        "resource_id",
        type=str,
        nargs="?",
        default=None,
        help="resource id (or name)",
    )

    return parser


def main():
    parser = _setup_parser()
    args = parser.parse_args()

    db = ForgeDB(overwrite=args.overwrite)
    if args.api is not None:
        db.set_api(args.api)

    api = ForgeApi(db.get_api())
    resource_type = args.resource_type
    if args.command in ["get", "delete", "upload", "download"]:
        if args.resource_id is not None:
            db.set_cursor(resource_type, args.resource_id)
        resource_id = db.get_cursor(resource_type)

        if args.command == "get":
            resource = api.get(resource_type, resource_id)
            db.set_cursor(resource_type, resource_id)
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
            config = read_config(args.config_path)
            if resource_type == "capture":
                config["input"] = db.get_cursor("input")
                config["session"] = db.get_cursor("session")
            elif resource_type == "snapshot":
                config["capture"] = db.get_cursor("capture")
            resource = api.create(resource_type, config)
            db.set_cursor(resource_type, resource["id"])
            print(f"created {resource_type}: {json.dumps(resource, indent=4)}")
            if resource_type == "capture":
                capture = resource
                session = api.get("session", capture["session"])
                _create_manifest(capture, session)
