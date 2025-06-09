from argparse import ArgumentParser
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from numpy import typing as npt
import sounddevice as sd
import wavio

from core.db import ForgeDB
from core.util import read_config

from capture_tool.audio import (
    vrms_to_dbu,
    calculate_latency,
    process_recordings,
)
from capture_tool.interface import AudioInterface
from capture_tool.stream import SineWaveStream, SendCalibrationStream, ReturnCalibrationStream, CaptureStream
from capture_tool.voltmeter import measure_acrms


def _print_interfaces() -> None:
    print(sd.query_devices())


def _print_interface(device: int) -> None:
    interface = sd.query_devices(device)
    for key, value in dict(interface).items():
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


def _write_wav(path: Path, data: npt.NDArray[np.int32], samplerate: int) -> None:
    wavio.write(
        str(path),
        data,
        samplerate,
        sampwidth=3,
    )


def _calibrate_send(
    interface: AudioInterface,
    send_level_dbfs: float = -3.0,
) -> None:
    if not interface._send_calibrated:
        print("send level calibration required. verify interface send is only connect to the voltmeter.")
        input("press enter to start send level calibration...")
        print("starting send level calibration...")
        stream = SendCalibrationStream(interface, level_dbfs=send_level_dbfs)
        with stream:
            send_level_dbu = vrms_to_dbu(measure_acrms())
        interface.set_send_level_dbu(send_level_dbu, send_level_dbfs)
        print("send level calibration complete")
        print("calibration value saved to config in capture directory")
        print("copy the following values to the supplied config file to skip calibration in the future")
    else:
        print("send level calibration not required")
        print("the following values were supplied config file, skipping calibration")
    print(f'"send_level_dbu ": {interface.send_level_dbu:f}')
    print("recalibrate following any settings (gain) or hardware changes")


def _calibrate_returns(
    interface: AudioInterface,
    send_level_dbfs: float = -3.0,
) -> None:
    if interface.return_levels_dbu is None:
        print("return level calibration required. connect the send output to each return channel one at a time")
        input("press enter to start return level calibration...")
        print("starting return levels calibration...")
        for i in range(interface.num_returns):
            input(f"channel {i + 1} - press enter to continue")
            stream = ReturnCalibrationStream(interface, send_level_dbfs)
            with stream:
                while not stream.done.wait(timeout=1.0):
                    pass
        interface.set_return_levels_dbu(
            send_level_dbfs,
            stream.get_return_levels(),
        )
        print("return level calibration complete")
        print("send level calibration complete")
        print("calibration value saved to config in capture directory")
        print("copy the following values to the supplied config file to skip calibration in the future")
    else:
        print("return level calibration not required")
        print("the following values were supplied config file, skipping calibration")
    print(f'"_return_levels_dbu ": {interface.return_levels_dbu:f}')
    print("recalibrate following any settings (gain) or hardware changes")


def _plot_latency(
    channel: int,
    samplerate: int,
    send_audio: npt.NDArray[np.int32],
    return_audio: npt.NDArray[np.int32],
    processed_return_audio: npt.NDArray[np.int32],
    channel_delays: list[int],
    channel_inversions: list[bool],
) -> None:
    samples = samplerate * 5
    plt.figure(figsize=(16, 5))
    plt.plot(
        np.divide(send_audio[:samples], np.max(send_audio[:samples])),
        label="reamp",
    )
    plt.plot(
        np.divide(return_audio[:samples, channel], np.max(return_audio[:samples, channel])),
        linestyle="--",
        label="raw recording",
    )
    plt.plot(
        np.divide(processed_return_audio[:samples, channel], np.max(processed_return_audio[:samples, channel])),
        linestyle="-.",
        label="processed recording",
    )
    plt.title(
        f"channel={channel} | base delay={channel_delays[0]} | channel_delay={channel_delays[channel]} | invert={channel_inversions[channel]}"
    )
    plt.legend()
    plt.show(block=True)


def _test_tone(interface: AudioInterface, unit_str: str, level: float) -> None:
    if unit_str == "dbfs":
        if level is None:
            level = -3
    elif unit_str == "dbu":
        _calibrate_send(interface, send_level_dbfs=-3.0)
        if level is None:
            level = interface.send_dbu_to_dbfs(-3)
        else:
            level = -3

    stream = SineWaveStream(interface, level_dbfs=level)

    with stream:
        print("enter 1 to increase output level, 2 to decrease output level, q to quit")
        control = "0"
        while control != "q":
            print(f"output level: {stream.get_send_level()} {unit_str}")
            if control == "1":
                stream.increase_send_level()
            elif control == "2":
                stream.decrease_send_level()
            elif control == "0" or control == "q":
                pass
            else:
                print("invalid input")
            control = input("> ")


def _capture(
    interface: AudioInterface,
    manifest: dict,
    input_wav: wavio.Wav,
    capture_dir: Path,
    no_show: bool = False,
) -> npt.NDArray[np.int32]:
    stream = CaptureStream(interface, input_wav, manifest["level_dbu"])

    print("verify interface send and returns are connected to the device to be modeled")
    input("press enter to start capture...")
    try:
        with stream:
            output_str = " | ".join(f"{dbu:3.2f}" for dbu in stream.get_return_levels())
            print(f"{stream.send_audio.get_time()} / {stream.send_audio.get_duration()} - {output_str}          ")
    except KeyboardInterrupt:
        print(f"capture manually stopped at {stream.send_audio.get_time()} / {stream.send_audio.get_time()}")
        raise KeyboardInterrupt

    channel_delays, channel_inversions = calculate_latency(
        stream.send_audio.unscaled_audio,
        stream.return_audio,
        stream.send_audio.samplerate,
    )
    processed_return_audio = process_recordings(
        stream.send_audio.unscaled_audio,
        stream.return_audio,
        channel_delays,
        channel_inversions,
    )

    if not no_show:
        for i in range(interface.num_returns):
            _plot_latency(
                i,
                stream.send_audio.samplerate,
                stream.send_audio.unscaled_audio,
                stream.return_audio,
                processed_return_audio,
                channel_delays,
                channel_inversions,
            )

    # Save the raw and processed recordings to two separate wav files
    # The number of channels in the wav file is equal to the number of return channels
    _write_wav(
        Path(capture_dir, "recording-raw.wav"),
        stream.return_audio,
        stream.send_audio.samplerate,
    )
    _write_wav(
        Path(capture_dir, f"recording-processed.wav"),
        processed_return_audio,
        stream.send_audio.samplerate,
    )

    return stream.return_audio


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("interfaces", help="List audio interfaces")
    interface_parser = subparsers.add_parser("interface")
    interface_parser.add_argument("interface", nargs="?", type=int, default=None, help="interface id")

    testtone_parser = subparsers.add_parser("testtone", help="Generate a test tone")
    testtone_parser.add_argument("type", nargs="?", type=str, default="dbfs", choices=["dbfs", "dbu"])
    testtone_parser.add_argument(
        "--level", type=float, required=False, help="level in dbfs or dbu. defaults to -3 for dbfs and 3 for dbu"
    )

    calibrate_parser = subparsers.add_parser("calibrate", help="Calibrate the interface")

    capture_parser = subparsers.add_parser("run", help="Run a capture")
    capture_parser.add_argument("manifest", type=str, help="path to capture manifest or parent dir to run")
    capture_parser.add_argument("--no-show", action="store_true", help="Skip plotting latency info")

    args = parser.parse_args()

    db = ForgeDB()
    interface_config = db.get_interface()
    if args.command == "interfaces":
        _print_interfaces()
    elif args.command == "interface":
        device = args.interface if args.interface else interface_config["device"]
        _print_interface(device)
    elif args.command == "testtone":
        interface = AudioInterface(interface_config)
        _test_tone(interface, args.type, args.level)
    elif args.command == "calibrate":
        interface = AudioInterface(interface_config)
        _calibrate_send(interface)
        db.set_interface(interface.get_config())
    elif args.command == "run":
        interface = AudioInterface(interface_config)

        manifest_path = Path(args.capture_manifest)
        if not manifest_path.exists():
            raise FileNotFoundError(f"capture dir {manifest_path} does not exist")
        elif not manifest_path.is_dir():
            manifest_path = Path(manifest_path, "manifest.json")
        output_dir = manifest_path.parent

        manifest = read_config(manifest_path)
        input_wav = wavio.read(Path(output_dir.parent, "inputs", manifest["input_id"]))
        return_audio = _capture(interface, manifest, input_wav, output_dir, no_show=args.no_show)
        _write_wav(
            Path(output_dir, "recording-raw.wav"),
            return_audio,
            input_wav.rate,
        )
