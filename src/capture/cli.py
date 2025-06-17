from argparse import ArgumentParser
from pathlib import Path

import wavio

from core.db import ForgeDB
from core.interface import AudioInterface
from core.stream import SineWaveStream, CaptureStream
from capture.manifest import CaptureManifest


DEFAULT_FREQ = 1000  # Hz
DEFAULT_SAMPLERATE = 48000  # Hz
DEFAULT_LEVEL_DBFS = -12.0  # dBFS


def _setup_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Capture tool")
    subparsers = parser.add_subparsers(dest="command")

    tone_parser = subparsers.add_parser("test_tone", help="Generate a test tone")
    tone_parser.add_argument(
        "--level",
        type=float,
        default=DEFAULT_LEVEL_DBFS,
        help="output level in dBFS",
    )
    tone_parser.add_argument(
        "--level_dbu",
        type=float,
        default=None,
        help="output level in dBu (overrides --level)",
    )
    tone_parser.add_argument(
        "--freq",
        type=int,
        default=DEFAULT_FREQ,
        help="frequency in Hz",
    )
    tone_parser.add_argument(
        "--samplerate",
        type=int,
        default=DEFAULT_SAMPLERATE,
        help="samplerate in Hz",
    )

    capture_parser = subparsers.add_parser("run", help="Run a capture")
    capture_parser.add_argument(
        "manifest",
        type=str,
        help="path to capture manifest or parent dir to run",
    )
    capture_parser.add_argument(
        "--no-show",
        action="store_true",
        help="Skip plotting latency info",
    )

    return parser


def main():
    parser = _setup_parser()
    args = parser.parse_args()
    command: str = args.command

    db = ForgeDB()
    interface_config = db.get_interface()

    interface = AudioInterface(interface_config)

    if command == "test_tone":
        freq: int = args.freq
        samplerate: int = args.samplerate
        level_dbfs: float = args.level
        if args.level_dbu is not None:
            level_dbfs = interface.send_dbu_to_dbfs(args.level_dbu)

        stream = SineWaveStream(interface, freq, samplerate, level_dbfs)
        with stream:
            print("enter 1 to increase output level, 2 to decrease output level, q to quit")
            control = "0"
            while control != "q":
                msg = f"output level: {stream.get_send_level():.2f} dBFS"
                if stream.interface.send_calibrated:
                    msg += f" ({stream.interface.send_dbfs_to_dbu:.2f} dBu)"
                print(msg)

                if control != "q":
                    try:
                        control = float(control)
                        stream.adjust_send_level(control)
                    except:
                        print("invalid input")
                control = input("> ")

    elif command == "run":
        manifest_path = Path(args.manifest)
        manifest = CaptureManifest(manifest_path)
        stream = CaptureStream(interface, manifest.input_data, manifest.samplerate, manifest.level_dbu)

        print("verify interface send and returns are connected to the device to be modeled")
        input("press enter to start capture...")
        try:
            with stream:
                output_str = " | ".join(f"{dbu:3.2f}" for dbu in stream.get_return_levels())
                print(f"{stream.send_audio.get_time()} / {stream.send_audio.get_duration()} - {output_str}          ")
        except KeyboardInterrupt:
            print(f"capture manually stopped at {stream.send_audio.get_time()} / {stream.send_audio.get_time()}")
            raise KeyboardInterrupt

        for i in range(len(manifest.channels)):
            channel = manifest.channels[i]
            path = Path(manifest.output_dir, f"{channel}.wav")
            wavio.write(
                str(path),
                stream.return_audio[:, i],
                manifest.samplerate,
                sampwidth=3,
            )
