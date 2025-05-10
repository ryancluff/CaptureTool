from argparse import ArgumentParser
import hashlib
import json
import numpy as np
from pathlib import Path
import wavio

from forge_cli.api import ForgeApi

RESOURCES = ["input", "session", "capture", "snapshot"]
RESOURCES_PLURAL = ["inputs", "sessions", "captures", "snapshots"]

FORGE_DIR = ".forge"
SESSIONS_DIR = "sessions"
CAPTURES_DIR = "captures"
INPUTS_DIR = "inputs"

INIT_API_CONFIG = {
    "host": "localhost",
    "port": 8000,
    "protocol": "http",
}

INIT_SELECTED_CONFIG = {
    "session": None,
    "capture": None,
    "input": None,
}

INIT_INTERFACE_CONFIG = {
    "device": 4,
    "samplerate": 48000,
    "blocksize": 512,
    "send_channel": 1,
    "frequency": 1000,
}


def _read_config(
    path: Path,
) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
    return config


def _write_config(
    output_dir: Path,
    config: dict,
    name: str = "config",
    overwrite: bool = False,
) -> None:
    config_path = Path(output_dir, name + ".json")
    if not config_path.exists() or overwrite:
        with open(config_path, "w") as fp:
            json.dump(config, fp, indent=4)


def _init() -> Path:
    forge_dir = Path(FORGE_DIR)
    forge_dir.mkdir(exist_ok=True)
    sessions_dir = Path(forge_dir, SESSIONS_DIR)
    sessions_dir.mkdir(exist_ok=True)
    inputs_dir = Path(forge_dir, INPUTS_DIR)
    inputs_dir.mkdir(exist_ok=True)
    _write_config(
        forge_dir,
        INIT_API_CONFIG,
        name="api",
    )
    _write_config(
        forge_dir,
        INIT_INTERFACE_CONFIG,
        name="interface",
    )
    _write_config(
        forge_dir,
        INIT_SELECTED_CONFIG,
        name="selected",
    )
    return forge_dir


def _create_session_dir(
    session_resource: dict,
) -> Path:
    session_dir = Path(FORGE_DIR, SESSIONS_DIR, session_resource["id"])
    session_dir.mkdir(exist_ok=False)
    captures_dir = Path(session_dir, CAPTURES_DIR)
    captures_dir.mkdir(exist_ok=False)
    return session_dir


def _create_capture_dir(
    capture_resource: dict,
) -> Path:
    capture_dir = Path(FORGE_DIR, SESSIONS_DIR, capture_resource["session"], CAPTURES_DIR, capture_resource["id"])
    capture_dir.mkdir(exist_ok=False)
    return capture_dir


def _write_wav(path: Path, data: np.array, samplerate: int) -> None:
    wavio.write(
        str(path),
        data,
        samplerate,
        sampwidth=3,
    )


def _get_selected(resource: str) -> str:
    with open(Path(FORGE_DIR, "selected.json"), "r") as fp:
        selected = json.load(fp)
    return selected.get(resource)


def _select(resource: str, resource_id: str) -> None:
    with open(Path(FORGE_DIR, "selected.json"), "r") as fp:
        selected = json.load(fp)
    selected[resource] = resource_id
    with open(Path(FORGE_DIR, "selected.json"), "w") as fp:
        json.dump(selected, fp, indent=4)


def cli():
    parser = ArgumentParser(description="forge cli")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Set up persistent forge directories and api config")

    list_parser = subparsers.add_parser("list", help="List forge resources")
    list_parser.add_argument("resource", type=str, choices=RESOURCES_PLURAL, help="Resource to list")

    get_parser = subparsers.add_parser("get", help="Get a forge resource")
    get_parser.add_argument("resource", type=str, choices=RESOURCES, help="Resource to get")
    get_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="ID of the resource to get")

    delete_parser = subparsers.add_parser("delete", help="Delete a forge resource")
    delete_parser.add_argument("resource", type=str, choices=RESOURCES, help="Resource to delete")
    delete_parser.add_argument("resource_id", type=str, nargs="?", default=None, help="ID of the resource to delete")

    create_parser = subparsers.add_parser("create", help="Create a new forge resource")
    create_subparsers = create_parser.add_subparsers(dest="resource")

    create_input_subparser = create_subparsers.add_parser("input", help="Create a new input resource")
    create_input_subparser.add_argument("file_path", type=str, help="Path to input file")
    create_input_subparser.add_argument("--name", type=str, default=None, help="Name of the input resource")
    create_input_subparser.add_argument("--description", type=str, default="", help="Description of the input resource")

    create_session_subparser = create_subparsers.add_parser("session", help="Create a new session resource")
    create_session_subparser.add_argument("config_path", type=str, help="Path to session config file")

    create_capture_subparser = create_subparsers.add_parser("capture", help="Create a new capture resource")
    create_capture_subparser.add_argument("config_path", type=str, help="Path to capture config file")

    args = parser.parse_args()

    if args.command == "init":
        _init()
        print(f"forge directory created at: {FORGE_DIR}. config files created with default values")
        print(f"make adjustments to {FORGE_DIR}/api.json and {FORGE_DIR}/interface.json as needed")
    else:
        forge_dir = Path(FORGE_DIR)
        if not forge_dir.exists():
            print(f"forge directory not found at: {forge_dir}. run `init` first")
            return
        api = ForgeApi(_read_config(Path(forge_dir, "api.json")))
        if args.command == "list":
            if args.resource == "inputs":
                resources = api.list_inputs()
            elif args.resource == "sessions":
                resources = api.list_sessions()
            elif args.resource == "captures":
                resources = api.list_captures()
            elif args.resource == "snapshots":
                raise NotImplementedError("list snapshots not implemented")
            print(f"{args.resource}: {json.dumps(resources, indent=4)}")
        elif args.command == "get":
            if args.resource_id is None:
                resource_id = _get_selected(args.resource)
                if resource_id is None:
                    print(f"no {args.resource} selected")
                    return
            else:
                resource_id = args.resource_id
            if args.resource == "input":
                resource = api.get_input(resource_id)
            elif args.resource == "session":
                resource = api.get_session(resource_id)
            elif args.resource == "capture":
                resource = api.get_capture(resource_id)
            elif args.resource == "snapshot":
                raise NotImplementedError("get snapshot not implemented")
            _select(args.resource, resource_id)
            print(f"{args.resource}: {json.dumps(resource, indent=4)}")
        elif args.command == "delete":
            if args.resource_id is None:
                resource_id = _get_selected(args.resource)
                if resource_id is None:
                    print(f"no {args.resource} selected")
                    return
            else:
                resource_id = args.resource_id
            if args.resource == "input":
                resource = api.delete_input(resource_id)
            elif args.resource == "session":
                resource = api.delete_session(resource_id)
            elif args.resource == "capture":
                resource = api.delete_capture(resource_id)
            elif args.resource == "snapshot":
                raise NotImplementedError("delete snapshot not implemented")
            print(f"deleted {args.resource}: {json.dumps(resource, indent=4)}")
        elif args.command == "create":
            if args.resource == "input":
                with open(args.file_path, "rb") as fp:
                    file_hash = hashlib.file_digest(fp, "sha256").hexdigest()
                config = {
                    "name": args.name if args.name else args.file_path.split("/")[-1],
                    "description": args.description,
                    "hash": file_hash,
                }
                resource = api.create_input(config)
                resource = api.upload_input(resource["id"], args.file_path)
                _select("input", resource["id"])
            elif args.resource == "session":
                session_config = _read_config(args.config_path)
                resource = api.create_session(session_config)
                session_dir = _create_session_dir(resource)
                _write_config(session_dir, resource, "session")
                _select("session", resource["id"])
            elif args.resource == "capture":
                capture_config = _read_config(args.config_path)
                capture_config["session"] = _get_selected("session")
                capture_config["input"] = _get_selected("input")
                resource = api.create_capture(capture_config)
                capture_dir = _create_capture_dir(resource)
                _write_config(capture_dir, resource, "capture")
                _select("capture", resource["id"])
            elif args.resource == "snapshot":
                raise NotImplementedError("create snapshot not implemented")
            print(f"created {args.resource}: {json.dumps(resource, indent=4)}") 


if __name__ == "__main__":
    cli()
