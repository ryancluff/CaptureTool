import json
from argparse import ArgumentParser
from pathlib import Path
from sounddevice import query_devices

from capture_tool.capture import Capture
from capture_tool.interface import Interface
from capture_tool.util import timestamp


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-interfaces")

    session_parser = subparsers.add_parser("session")
    session_parser.add_argument("interface_config_path", type=str)
    session_parser.add_argument("device_config_path", type=str)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("session_path", type=str)
    capture_parser.add_argument("capture_config_path", type=str)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("session_path", type=str)

    args = parser.parse_args()

    if args.command == "list-interfaces":
        print(query_devices())
    elif args.command == "session":
        # Load interface and device configs
        with open(args.interface_config_path, "r") as fp:
            interface_config = json.load(fp)
        with open(args.device_config_path, "r") as fp:
            device_config = json.load(fp)

        # Attach path args to each respective config
        interface_config["path"] = args.interface_config_path
        device_config["path"] = args.device_config_path

        # Create sessions directory if it doesn't already exist
        sessions_dir = Path("sessions")
        sessions_dir.mkdir(exist_ok=True)

        # Validate the interface config and then run calibration
        interface = Interface(interface_config)
        # interface.calibrate()

        # Create a directory for the new session
        # Uses a timestamp for the directory name
        session_dir = Path(sessions_dir, timestamp())
        session_dir.mkdir(exist_ok=False)

        # Save the interface and device config to the session directory
        with open(Path(session_dir, "interface.json"), "w") as fp:
            json.dump(interface_config, fp, indent=4)
        with open(Path(session_dir, "device.json"), "w") as fp:
            json.dump(device_config, fp, indent=4)
    elif args.command == "capture":
        # Load interface, device, and capture configs
        with open(Path(args.session_path, "interface.json"), "r") as fp:
            interface_config = json.load(fp)
        with open(Path(args.session_path, "device.json"), "r") as fp:
            device_config = json.load(fp)
        with open(args.capture_config_path, "r") as fp:
            capture_config = json.load(fp)

        # Attach path arg to capture config
        capture_config["path"] = args.capture_config_path

        # Create captures directory if it doesn't already exist
        captures_dir = Path(args.session_path, "captures")
        captures_dir.mkdir(exist_ok=True)

        # Validate the interface and capture configs
        interface = Interface(interface_config)
        capture = Capture(capture_config)

        # Create a directory for the new capture with the session directory
        capture_dir = Path(captures_dir, timestamp())
        capture_dir.mkdir(exist_ok=False)

        # Save the interface, device, and capture configs to the capture directory
        with open(Path(captures_dir, "interface.json"), "w") as fp:
            json.dump(interface_config, fp, indent=4)
        with open(Path(captures_dir, "device.json"), "w") as fp:
            json.dump(device_config, fp, indent=4)
        with open(Path(captures_dir, "capture.json"), "w") as fp:
            json.dump(capture_config, fp, indent=4)

        # Run the capture and save to the capture directory
        capture.run(interface, Path(capture_dir, "recording.wav"))

    elif args.command == "resume":
        raise NotImplementedError("Resume not yet implemented")
    elif args.command == "passthrough":
        with open(Path(args.session_path, "interface.json"), "r") as fp:
            interface_config = json.load(fp)

        interface = Interface(interface_config)

        if interface.reamp_dbu is None:
            raise RuntimeError("Interface not calibrated")

        interface.passthrough()

    else:
        raise NotImplementedError(f"command {args.command} not implemented")

    print("done")
    print("")


if __name__ == "__main__":
    cli()
