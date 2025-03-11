import json
from argparse import ArgumentParser
from pathlib import Path
import sounddevice as sd
import wavio

from capture_tool.interface import AudioInterface
from capture_tool.util import timestamp


def _read_config(path: Path) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
        config["path"] = str(path)
    return config


def _write_config(
    capture_dir: Path,
    config: dict,
    name: str = "interface",
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


def _calibrate(interface: AudioInterface) -> tuple[float, float]:
    pause_after_calibration = False
    if interface.reamp_delta is None:
        pause_after_calibration = True
        print("reamp calibration required. verify reamp output is only connect to the voltmeter.")
        input("press enter to start reamp calibration...")
        print("calibrating reamp output...")
        reamp_delta = interface.calibrate_reamp()
        print(f"target reamp level: {interface.output_level_max_dbu:.2f} dBu")
        print(f"calculated input delta (dbu - dbfs): {interface.reamp_delta:.2f}")
        print("calibration complete")
        print(f'"reamp_delta": {interface.reamp_delta:.2f}')
    else:
        reamp_delta = interface.reamp_delta
        print("reamp calibration not required")
        print(f"configured input delta (dbu - dbfs): {interface.reamp_delta:.2f}")

    if interface.input_deltas is None:
        pause_after_calibration = True
        print("input calibration required")
        print("calibrating input channels...")
        print("connect the reamp output to each input channel one at a time")
        input_deltas = interface.calibrate_inputs()
        print(f"calculated reamp -> input deltas (dbfs): {interface.reamp_delta:.2f}")
        print("calibration complete")
    else:
        input_deltas = interface.input_deltas
        print("input calibration not required")
        print(f"configured reamp -> input deltas (dbfs): {interface.input_deltas:.2f}")

    if pause_after_calibration:
        print("calibration values saved to interface config in capture directory")
        print("copy these values to the supplied interface config file to skip calibration in the future")
        print("recalibrate following any settings (gain) or hardware changes")
        input("press enter to continue...")

    return reamp_delta, input_deltas


def _passthrough(interface: AudioInterface) -> None:
    interface.passthrough()


def cli():
    parser = ArgumentParser(description="Capture tool")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list-interfaces")
    list_parser.add_argument("interface", nargs="?", type=int, default=None)

    capture_parser = subparsers.add_parser("capture", help="Run a capture")
    capture_parser.add_argument("interface_config_path", type=str)
    capture_parser.add_argument("device_config_path", nargs="?", type=str, default=None)

    reamp_parser = subparsers.add_parser("reamp", help="Loop reamp output without recording")
    reamp_parser.add_argument("interface_config_path", type=str)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("interface_config_path", type=str)

    testtone_parser = subparsers.add_parser("testtone", help="Generate a test tone")
    testtone_parser.add_argument("interface_config_path", type=str)
    testtone_parser.add_argument("type", nargs="?", type=str, default="dbfs")

    args = parser.parse_args()
    if args.command == "list-interfaces":
        if args.interface:
            print(sd.query_devices(args.interface))
            print("")
            samplerates = [32000, 44100, 48000, 88200, 96000, 128000, 192000]
            supported_samplerates = []
            for fs in samplerates:
                try:
                    sd.check_output_settings(device=args.interface, samplerate=fs)
                except Exception as e:
                    pass
                else:
                    supported_samplerates.append(fs)
            print("supported samplerates: " + str(supported_samplerates))
        else:
            print(sd.query_devices())
    elif args.command == "capture":
        # read configs, create dirs
        interface_config = _read_config(args.interface_config_path)
        if args.device_config_path:
            device_config = _read_config(args.device_config_path)
        captures_dir = _create_captures_dir()
        capture_dir = _create_capture_dir(captures_dir)

        interface = AudioInterface(interface_config)
        # Run calibration if needed
        interface_config["reamp_delta"] = _calibrate(interface)
        _write_config(capture_dir, interface_config)
        if args.device_config_path:
            _write_config(capture_dir, device_config, "device")
        raw_recording, processed_recording = interface.capture(plot_latency=True)
        # Save the raw recording to a single wav file
        # The number of channels in the wav file is equal to the number of input channels
        wavio.write(
            str(Path(capture_dir, "recording-raw.wav")),
            raw_recording,
            interface.input_wav.rate,
            sampwidth=3,
        )
        # Save the processed recording data
        # Each channel is saved to a separate mono wav file
        for i in range(len(interface.interface.channels["input"])):
            channel = interface.interface.channels["input"][i]
            wavio.write(
                str(Path(capture_dir, f"recording-{channel}.wav")),
                processed_recording[:, i],
                interface.input_wav.rate,
                sampwidth=3,
            )
    elif args.command == "reamp":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        interface_config["reamp_delta"], interface_config["input_deltas"] = _calibrate(interface)
    elif args.command == "passthrough":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        interface_config["reamp_delta"], interface_config["input_deltas"] = _calibrate(interface)
        _passthrough(interface)
    elif args.command == "testtone":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        if args.type == "dbfs":
            interface.testtone()
        elif args.type == "dbu":
            _calibrate(interface)
            interface.testtone_dbu()
    print("done")


if __name__ == "__main__":
    cli()
