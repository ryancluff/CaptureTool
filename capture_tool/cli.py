import json
import os
from argparse import ArgumentParser
from pathlib import Path
from sounddevice import query_devices


from capture_tool.util import timestamp
from capture_tool.interface import Interface
from capture_tool.capture import Capture


def _save_configs(configs: dict, outdir: Path):
    if not outdir.exists():
        raise RuntimeError(f"No output location found at {outdir}")

    for basename, config in configs:
        with open(Path(outdir, f"config_{basename}.json"), "w") as fp:
            json.dump(config, fp, indent=4)


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    calibrate_parser = subparsers.add_parser("calibrate", help="Calibrate interface")
    calibrate_parser.add_argument("interface_config_path", type=str)

    start_parser = subparsers.add_parser("start", help="Start new capture")
    start_parser.add_argument("interface_config_path", type=str)
    start_parser.add_argument("capture_config_path", type=str)
    start_parser.add_argument("outdir", type=str)

    resume_parser = subparsers.add_parser("resume", help="Resume previous capture")
    resume_parser.add_argument("resume_outdir", type=str)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("interface_config_path", type=str)

    subparsers.add_parser("list_devices", help="List available devices")

    args = parser.parse_args()

    configs = dict()

    if args.command == "list_devices":
        print(query_devices())
    elif args.command == "calibrate":
        with open(args.interface_config_path, "r") as fp:
            configs["interface"] = json.load(fp)

        interface = Interface(configs["interface"])
        interface.calibrate()
    elif args.command == "start":
        outdir = Path(args.outdir, timestamp())
        outdir.mkdir(parents=True, exist_ok=False)

        with open(args.interface_config_path, "r") as fp:
            configs["interface"] = json.load(fp)
        with open(args.capture_config_path, "r") as fp:
            configs["capture"] = json.load(fp)
        _save_configs(configs, outdir)

        interface = Interface(configs["interface"])
        capture = Capture(configs["capture"])
        if interface._output_level is None:
            interface.calibrate()

        capture.run(interface)
    elif args.command == "resume":
        raise NotImplementedError("Resume not yet implemented")
    elif args.command == "passthrough":
        with open(args.interface_config_path, "r") as fp:
            configs["interface"] = json.load(fp)

        interface = Interface(configs["interface"])
        if interface._output_level is None:
            interface.calibrate()

        interface.passthrough()

    print("done")
    print("")


if __name__ == "__main__":
    cli()
