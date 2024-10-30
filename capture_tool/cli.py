import json
from argparse import ArgumentParser
from pathlib import Path
from sounddevice import query_devices


from capture_tool.util import timestamp
from capture_tool.interface import Interface
from capture_tool.capture import Capture


def _capture_tool(interface_config: dict, capture_config: dict, outdir: Path):
    if not outdir.exists():
        raise RuntimeError(f"No output location found at {outdir}")

    # Write
    for basename, config in (
        ("interface", interface_config),
        ("capture", capture_config),
    ):
        with open(Path(outdir, f"config_{basename}.json"), "w") as fp:
            json.dump(config, fp, indent=4)

    interface = Interface(interface_config)
    interface.calibrate()

    capture = Capture(capture_config)
    capture.run(interface)


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers()

    start_parser = subparsers.add_parser("start", help="Start new capture")
    start_parser.add_argument("interface_config_path", type=str)
    start_parser.add_argument("capture_config_path", type=str)
    start_parser.add_argument("outdir", type=str)

    resume_parser = subparsers.add_parser("resume", help="Resume previous capture")
    resume_parser.add_argument("resume_outdir", type=str)

    args = parser.parse_args()

    def ensure_outdir(outdir: str) -> Path:
        outdir = Path(outdir, timestamp())
        outdir.mkdir(parents=True, exist_ok=False)
        return outdir

    outdir = ensure_outdir(args.outdir)
    with open(args.interface_config_path, "r") as fp:
        interface_config = json.load(fp)
    with open(args.capture_config_path, "r") as fp:
        capture_config = json.load(fp)

    _capture_tool(interface_config, capture_config, outdir)


if __name__ == "__main__":
    cli()
