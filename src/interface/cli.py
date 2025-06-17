from argparse import ArgumentParser

import sounddevice as sd

from core.db import ForgeDB


SAMPLERATES = [32000, 44100, 48000, 88200, 96000, 128000, 192000]  # Hz


def _setup_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Forge Interface CLI")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List audio interfaces")

    inspect_parser = subparsers.add_parser("inspect", help="Show audio interface details")
    inspect_parser.add_argument(
        "interface",
        nargs="?",
        type=int,
        default=None,
        help="interface id",
    )

    return parser


def main():
    parser = _setup_parser()
    args = parser.parse_args()

    db = ForgeDB()
    interface_config = db.get_interface()
    if args.command == "list":
        print(sd.query_devices())

    elif args.command == "inspect":
        device = args.interface if args.interface else interface_config["device"]

        interface = sd.query_devices(device)
        for key, value in dict(interface).items():
            print(f"{key}: {value}")
        supported_samplerates = []
        for fs in SAMPLERATES:
            try:
                sd.check_output_settings(device=device, samplerate=fs)
            except Exception as e:
                pass
            else:
                supported_samplerates.append(fs)
        print("supported samplerates: " + str(supported_samplerates))
