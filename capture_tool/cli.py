import json
from argparse import ArgumentParser
from pathlib import Path
import sounddevice as sd
import wavio

from capture_tool.capture import Capture
from capture_tool.interface import Interface
from capture_tool.util import timestamp


def _read_configs(
    interface_config_path: Path,
    capture_config_path: Path | None = None,
    device_config_path: Path | None = None,
) -> tuple[dict, dict | None, dict | None]:
    with open(interface_config_path, "r") as fp:
        interface_config = json.load(fp)
        interface_config["path"] = interface_config_path
    if capture_config_path is not None:
        with open(capture_config_path, "r") as fp:
            capture_config = json.load(fp)
            capture_config["path"] = capture_config_path
    else:
        capture_config = None
    if device_config_path is not None:
        with open(device_config_path, "r") as fp:
            device_config = json.load(fp)
            device_config["path"] = device_config_path
    else:
        device_config = None
    return interface_config, capture_config, device_config


def _write_configs(
    capture_dir: Path,
    interface_config: dict,
    capture_config: dict | None = None,
    device_config: dict | None = None,
) -> None:
    with open(Path(capture_dir, "interface.json"), "w") as fp:
        json.dump(interface_config, fp, indent=4)
    if capture_config is not None:
        with open(Path(capture_dir, "capture.json"), "w") as fp:
            json.dump(capture_config, fp, indent=4)
    if device_config is not None:
        with open(Path(capture_dir, "device.json"), "w") as fp:
            json.dump(device_config, fp, indent=4)


def _calibrate(interface: Interface) -> float:
    pause_after_calibration = False
    if interface.reamp_delta is None:
        pause_after_calibration = True
        print("reamp calibration required. verify reamp output is only connect to the voltmeter.")
        input("press enter to start reamp calibration...")
        print("calibrating reamp output...")
        reamp_delta = interface.calibrate_reamp()
        print(f"target reamp level: {interface.target_dbu:.2f} dBu")
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


def _passthrough(interface: Interface) -> None:
    interface.passthrough()


def create_captures_dir(path: str = "captures") -> Path:
    captures_dir = Path(path)
    captures_dir.mkdir(exist_ok=True)
    return captures_dir


def create_capture_dir(captures_dir: Path, path: str = timestamp()) -> Path:
    captures_dir = Path(captures_dir, path)
    captures_dir.mkdir(exist_ok=False)
    return captures_dir


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list-interfaces")
    list_parser.add_argument("interface", nargs="?", type=int, default=None)

    capture_parser = subparsers.add_parser("capture", help="Run a capture")
    capture_parser.add_argument("interface_config_path", type=str)
    capture_parser.add_argument("capture_config_path", type=str)
    capture_parser.add_argument("device_config_path", nargs="?", type=str, default=None)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("interface_config_path", type=str)

    args = parser.parse_args()

    if args.command == "list-interfaces":
        if args.interface is not None:
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
        capture_config, interface_config, device_config = _read_configs(
            args.interface_config_path,
            args.capture_config_path,
            args.device_config_path,
        )
        captures_dir = create_captures_dir()
        capture_dir = create_capture_dir(captures_dir)

        capture = Capture(capture_config, Interface(interface_config))
        # Run calibration if needed
        interface_config["reamp_delta"] = _calibrate(capture.interface)
        _write_configs(
            capture_dir,
            interface_config,
            capture_config,
            device_config,
        )
        raw_recording, processed_recording = capture.run(plot_latency=True)
        # Save the raw recording to a single wav file
        # The number of channels in the wav file is equal to the number of input channels
        wavio.write(
            str(Path(capture_dir, "recording-raw.wav")),
            raw_recording,
            capture.input_wav.rate,
            sampwidth=3,
        )
        # Save the processed recording data
        # Each channel is saved to a separate mono wav file
        for i in range(len(capture.interface.channels["input"])):
            channel = capture.interface.channels["input"][i]
            wavio.write(
                str(Path(capture_dir, f"recording-{channel}.wav")),
                processed_recording[:, i],
                capture.input_wav.rate,
                sampwidth=3,
            )
    elif args.command == "passthrough":
        interface_config = _read_configs(args.interface_config_path)
        interface = Interface(interface_config)
        interface_config["reamp_delta"], interface_config["input_deltas"] = _calibrate(interface)
        _passthrough(interface)
    print("done")


if __name__ == "__main__":
    cli()
