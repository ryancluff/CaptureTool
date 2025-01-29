import json
import os
from argparse import ArgumentParser
from pathlib import Path
from sounddevice import query_devices


from capture_tool.capture import Capture
from capture_tool.interface import Interface
from capture_tool.util import timestamp


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    interfaces_parser = subparsers.add_parser("interface")
    interfaces_subparsers = interfaces_parser.add_subparsers(dest="interfaces_subcommand")
    interfaces_subparsers.add_parser("list", help="List available audio interfaces")

    session_parser = subparsers.add_parser("session")
    session_subparsers = session_parser.add_subparsers(dest="session_subcommand")
    new_session_parser = session_subparsers.add_parser("new", help="Create a new session")
    new_session_parser.add_argument("interface_config_path", type=str)
    new_session_parser.add_argument("device_config_path", type=str)

    capture_parser = subparsers.add_parser("capture")
    capture_subparsers = capture_parser.add_subparsers(dest="capture_subcommand")
    new_capture_parser = capture_subparsers.add_parser("new", help="Create a new capture")
    new_capture_parser.add_argument("session_path", type=str)
    new_capture_parser.add_argument("capture_config_path", type=str)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("session_path", type=str)

    args = parser.parse_args()

    if args.command == "interface":
        if args.interfaces_subcommand == "list":
            print(query_devices())
        else:
            raise NotImplementedError(f"interface command {args.interfaces_subcommand} not implemented")
    elif args.command == "session":
        if args.session_subcommand == "new":
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

            # Instantiate the interface and then run calibration
            interface = Interface(interface_config)
            interface.calibrate()

            # Create a new directory for the new session
            # Uses a timestamp for the directory name
            session_dir = Path(sessions_dir, timestamp())
            session_dir.mkdir(exist_ok=False)

            # Save the interface and device config to the session directory
            with open(Path(session_dir, "interface.json"), "w") as fp:
                json.dump(interface_config, fp, indent=4)
            with open(Path(session_dir, "device.json"), "w") as fp:
                json.dump(device_config, fp, indent=4)
        else:
            raise NotImplementedError(f"session command {args.session_subcommand} not implemented")
    elif args.command == "capture":
        if args.capture_subcommand == "new":
            # Load interface, device, and capture configs
            with open(Path(args.session_path, "interface.json"), "r") as fp:
                interface_config = json.load(fp)
            with open(Path(args.session_path, "device.json"), "r") as fp:
                device_config = json.load(fp)
            with open(args.capture_config_path, "r") as fp:
                capture_config = json.load(fp)

            # Attach path arg to capture config
            capture_config["path"] = Path(args.session_path, "interface.json")

            # Create captures directory if it doesn't already exist
            captures_dir = Path(args.session_path, "captures")
            captures_dir.mkdir(exist_ok=True)



            interface = Interface(interface_config)
            capture = Capture(capture_config, capture_dir)

            capture_dir = Path(captures_dir, timestamp())
            capture_dir.mkdir(exist_ok=False)

            with open(Path(captures_dir, "interface.json"), "w") as fp:
                json.dump(interface_config, fp, indent=4)
            with open(Path(captures_dir, "device.json"), "w") as fp:
                json.dump(device_config, fp, indent=4)
            with open(Path(captures_dir, "capture.json"), "w") as fp:
                json.dump(capture_config, fp, indent=4)

            if interface.reamp_dbu is None:
                raise RuntimeError("Interface not calibrated")
            capture.run()
        else:
            raise NotImplementedError(f"capture subcommand {args.capture_subcommand} not implemented")
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
