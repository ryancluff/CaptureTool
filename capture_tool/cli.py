from argparse import ArgumentParser
import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sounddevice as sd
import wavio

from capture_tool.audio import (
    int_to_dbfs,
    v_rms_to_dbu,
    calculate_latency,
    process_recordings,
)
from capture_tool.interface import (
    ClipException,
    TestToneUnit,
    AudioInterface,
)
from capture_tool.util import timestamp


def _print_interface(device: int = None) -> None:
    if device:
        interface = sd.query_devices(device)
        for key, value in interface.items():
            print(f"{key}: {value}")
        samplerates = [32000, 44100, 48000, 88200, 96000, 128000, 192000]
        supported_samplerates = []
        for fs in samplerates:
            try:
                sd.check_output_settings(device=device, samplerate=fs)
            except Exception as e:
                pass
            else:
                supported_samplerates.append(fs)
        print("supported samplerates: " + str(supported_samplerates))
    else:
        print(sd.query_devices())


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
    calibration_changed = False
    if interface._send_level_dbu is None:
        calibration_changed = True
        print("reamp calibration required. verify reamp output is only connect to the voltmeter.")
        input("press enter to start reamp calibration...")
        print("calibrating reamp output...")
        _send_level_dbu = interface.calibrate_reamp()
        print(f"target reamp level: {interface.output_level_max_dbu:.2f} dBu")
        print(f"calculated input delta (dbu - dbfs): {interface._send_level_dbu:.2f}")
        print("calibration complete")
        print(f'"_send_level_dbu ": {interface._send_level_dbu:.2f}')
    else:
        _send_level_dbu = interface._send_level_dbu
        print("reamp calibration not required")
        print(f"configured input delta (dbu - dbfs): {interface._send_level_dbu:.2f}")

    if interface._return_level_dbu is None:
        calibration_changed = True
        print("input calibration required")
        print("calibrating input channels...")
        print("connect the reamp output to each input channel one at a time")
        _return_level_dbu = interface.calibrate_inputs()
        print(f"calculated reamp -> input deltas (dbfs): {interface._send_level_dbu:.2f}")
        print("calibration complete")
    else:
def _test_tone(config_path: Path, unit: TestToneUnit, level: float) -> None:
    config = _read_config(config_path)
    interface = AudioInterface(config)
    if unit == TestToneUnit.DBFS:
        if level is None:
            level = -3
    elif unit == TestToneUnit.DBU:
        _calibrate_send(interface, send_level_dbfs=-3.0)
        if level is None:
            level = 3

    stream, get_output_level_dbfs, increase_output_level, decrease_output_level = interface.get_test_tone_stream(
        level, unit
    )

    with stream:
        print("enter 1 to increase output level, 2 to decrease output level, q to quit")
        control = "0"
        while control != "q":
            print("output level: ", get_output_level_dbfs(), "dbfs" if unit == TestToneUnit.DBFS else "dbu")
            if control == "1":
                increase_output_level()
            elif control == "2":
                decrease_output_level()
            elif control == "0" or control == "q":
                pass
            else:
                print("invalid input")
            control = input("> ")


def cli():
    parser = ArgumentParser(description="Capture tool")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list-interfaces")
    list_parser.add_argument("interface", nargs="?", type=int, default=None)

    capture_parser = subparsers.add_parser("capture", help="Run a capture")
    capture_parser.add_argument("interface_config_path", type=str)

    reamp_parser = subparsers.add_parser("reamp", help="Loop reamp output without recording")
    reamp_parser.add_argument("interface_config_path", type=str)

    passthrough_parser = subparsers.add_parser("passthrough", help="Passthrough instrument audio")
    passthrough_parser.add_argument("interface_config_path", type=str)

    testtone_parser = subparsers.add_parser("testtone", help="Generate a test tone")
    testtone_parser.add_argument("interface_config_path", type=str)
    testtone_parser.add_argument("type", nargs="?", type=str, default="dbfs", choices=["dbfs", "dbu"])
    testtone_parser.add_argument("--level", type=float, required=False)

    args = parser.parse_args()
    if args.command == "list-interfaces":
        _print_interface(args.interface)
    elif args.command == "capture":
        # read configs, create dirs
        interface_config = _read_config(args.interface_config_path)
        captures_dir = _create_captures_dir()
        capture_dir = _create_capture_dir(captures_dir)

        interface = AudioInterface(interface_config)
        # Run calibration if needed
        interface_config["_send_level_dbu "] = _calibrate(interface)
        _write_config(capture_dir, interface_config)
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
        for i in range(len(interface.channels["input"])):
            channel = interface.channels["input"][i]
            wavio.write(
                str(Path(capture_dir, f"recording-{channel}.wav")),
                processed_recording[:, i],
                interface.input_wav.rate,
                sampwidth=3,
            )
    elif args.command == "reamp":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        interface_config["_send_level_dbu "], interface_config["_return_level_dbu"] = _calibrate(interface)
    elif args.command == "passthrough":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        interface_config["_send_level_dbu "], interface_config["_return_level_dbu"] = _calibrate(interface)
        _passthrough(interface)
    elif args.command == "testtone":
        _test_tone(args.config_path, args.type, args.level)


if __name__ == "__main__":
    cli()
