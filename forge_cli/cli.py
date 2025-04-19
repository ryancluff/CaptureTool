from argparse import ArgumentParser
import json
import numpy as np
from pathlib import Path
import wavio

from forge_cli.api import ForgeInput, ForgeSession, ForgeCapture, ForgeApi
from capture_tool.interface import AudioInterface
from capture_tool.util import timestamp


def _read_config(path: Path) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
        config["config_path"] = str(path)
    return config


def _write_config(
    capture_dir: Path,
    config: dict,
    name: str = "config",
) -> None:
    with open(Path(capture_dir, name + ".json"), "w") as fp:
        json.dump(config, fp, indent=4)


def _create_captures_dir(path: str = "captures") -> Path:
    captures_dir = Path(path)
    captures_dir.mkdir(exist_ok=True)
    return captures_dir


def _create_capture_dir(captures_dir: Path, path: str = timestamp()) -> Path:
    captures_dir = Path(captures_dir, path)
    captures_dir.mkdir(exist_ok=False)
    return captures_dir


def _write_wav(path: Path, data: np.array, samplerate: int) -> None:
    wavio.write(
        str(path),
        data,
        samplerate,
        sampwidth=3,
    )


def cli():
    parser = ArgumentParser(description="forge cli")
    parser.add_argument("--config", type=str, default=".forgecli.json", help="Path to the forge api config file")

    subparsers = parser.add_subparsers(dest="command")

    input_parser = subparsers.add_parser("input", help="Manage forge input files")
    input_command_parser = input_parser.add_subparsers(dest="input_command")
    input_list_parser = input_command_parser.add_parser("list", help="List input files in forge api")
    input_new_parser = input_command_parser.add_parser("new", help="Upload input file to forge api")
    input_new_parser.add_argument("input_config_path", type=str)

    session_parser = subparsers.add_parser("session", help="Manage forge sessions")
    session_command_parser = session_parser.add_subparsers(dest="session_command")
    session_list_parser = session_command_parser.add_parser("list", help="List sessions in forge api")
    session_get_parser = session_command_parser.add_parser("get", help="Get a session")
    session_get_parser.add_argument("session_id", type=str)
    session_new_parser = session_command_parser.add_parser("new", help="Create a new session")
    session_new_parser.add_argument("interface_config_path", type=str)
    session_new_parser.add_argument("session_config_path", type=str)

    capture_parser = subparsers.add_parser("capture", help="Manage or run a capture")
    capture_command_parser = capture_parser.add_subparsers(dest="capture_command")
    capture_list_parser = capture_command_parser.add_parser("list", help="List captures")
    capture_get_parser = capture_command_parser.add_parser("get", help="Get a capture")
    capture_get_parser.add_argument("capture_id", type=str)
    capture_run_parser = capture_command_parser.add_parser("run", help="Run a capture")
    capture_run_parser.add_argument("interface_config_path", type=str)
    capture_run_parser.add_argument("--no-show", action="store_true", help="Skip plotting latency info")

    args = parser.parse_args()

    if args.api_config is None:
        api = ForgeApi()
    else:
        api = ForgeApi(_read_config(args.api_config))

    if args.command == "input":
        if args.input_command == "list":
            inputs = api.list_inputs()
            print(f"inputs: {json.dumps(inputs, indent=4)}")
        elif args.input_command == "new":
            input_config = _read_config(args.input_config_path)
            input = ForgeInput(input_config)
            id = api.post_input(input)
            print(f"input uploaded with id: {id}")
    elif args.command == "session":
        if args.session_command == "list":
            sessions = api.list_sessions()
            print(f"sessions: {json.dumps(sessions, indent=4)}")
        elif args.session_command == "get":
            session = api.get_session(args.session_id)
            print(f"session: {json.dumps(session, indent=4)}")
        elif args.session_command == "new":
            session_config = _read_config(args.session_config_path)
            session = ForgeSession(session_config)
            interface_config = _read_config(args.interface_config_path)
            interface = AudioInterface(interface_config)
            session.config["channels"] = interface.channels["returns"]
            id = api.post_session(session)
            print(f"session created with id: {id}")
    elif args.command == "capture":
        if args.capture_command == "list":
            captures = api.list_captures()
            print(f"captures: {json.dumps(captures, indent=4)}")
        elif args.capture_command == "get":
            capture = api.get_capture(args.capture_id)
            print(f"capture: {json.dumps(capture, indent=4)}")
        elif args.capture_command == "new":

            _capture(args.interface_config_path, no_show=args.no_show)


if __name__ == "__main__":
    cli()
