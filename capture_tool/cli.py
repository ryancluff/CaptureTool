import json
from argparse import ArgumentParser
from pathlib import Path
import sounddevice as sd

from capture_tool.capture import Capture
from capture_tool.interface import Interface
from capture_tool.util import timestamp


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list-interfaces")
    list_parser.add_argument("--interface", type=int, required=False)

    capture_parser = subparsers.add_parser("capture", help="Run a capture")
    capture_parser.add_argument("capture_config_path", type=str)
    capture_parser.add_argument("interface_config_path", type=str)
    capture_parser.add_argument("--device_config_path", type=str, required=False)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("interface_config_path", type=str)

    args = parser.parse_args()

    if args.command == "list-interfaces":
        if args.interface is not None:
            print(sd.query_devices(args.interface))
            print("")

            samplerates = 32000, 44100, 48000, 88200, 96000, 128000, 192000

            supported_samplerates = []
            for fs in samplerates:
                try:
                    sd.check_output_settings(device=args.interface, samplerate=fs)
                except Exception as e:
                    print(fs, e)
                else:
                    supported_samplerates.append(fs)
            print("supported samplerates: " + str(supported_samplerates))
        else:
            print(sd.query_devices())
    elif args.command == "capture":
        # Load configs and attach path args to each respective config
        with open(args.capture_config_path, "r") as fp:
            capture_config = json.load(fp)
            capture_config["path"] = args.capture_config_path
        with open(args.interface_config_path, "r") as fp:
            interface_config = json.load(fp)
            interface_config["path"] = args.interface_config_path
        if args.device_config_path is not None:
            with open(args.device_config_path, "r") as fp:
                device_config = json.load(fp)
                device_config["path"] = args.device_config_path

        # Create captures directory if it doesn't already exist
        captures_dir = Path("captures")
        captures_dir.mkdir(exist_ok=True)

        # Validate the interface and capture configs
        interface = Interface(interface_config)
        capture = Capture(capture_config)

        interface_config["reamp_delta"] = interface.calibrate()

        input("Press enter to start capture...")
        print("")

        # Create a directory for the new capture
        # Uses a timestamp for the directory name
        capture_dir = Path(captures_dir, timestamp())
        capture_dir.mkdir(exist_ok=False)

        # Save interface, capture, and (optionally) device configs
        with open(Path(capture_dir, "capture.json"), "w") as fp:
            json.dump(capture_config, fp, indent=4)
        with open(Path(capture_dir, "interface.json"), "w") as fp:
            json.dump(interface_config, fp, indent=4)
        if args.device_config_path is not None:
            with open(Path(capture_dir, "device.json"), "w") as fp:
                json.dump(device_config, fp, indent=4)

        # Run the capture and save to the capture directory
        capture.run(interface, capture_dir)
    elif args.command == "passthrough":
        # Load interface config
        with open(Path(args.session_path, "interface.json"), "r") as fp:
            interface_config = json.load(fp)

        # Validate the interface config
        interface = Interface(interface_config)

        # Run calibration if needed
        if interface.reamp_delta is None:
            interface_config["reamp_delta"]= interface.calibrate()

        # Pass instrument audio from an input to the reamp output
        interface.passthrough()

    else:
        raise NotImplementedError(f"command {args.command} not implemented")

    print("done")
    print("")


if __name__ == "__main__":
    cli()
