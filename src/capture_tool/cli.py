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
from capture_tool.manifest import CaptureManifest
from capture_tool.stream import SineWaveStream, SineSweepStream, CaptureStream
from capture_tool.voltmeter import measure_acrms


DEFAULT_FREQ = 1000  # Hz
DEFAULT_FREQ_SWEEP_START = 20  # Hz
DEFAULT_FREQ_SWEEP_END = 20000  # Hz
DEFAULT_SAMPLERATE = 48000  # Hz
DEFAULT_LEVEL_DBFS = -3.0  # dBFS

SAMPLERATES = [32000, 44100, 48000, 88200, 96000, 128000, 192000]  # Hz


def _print_interfaces() -> None:
    print(sd.query_devices())


def _print_interface(device: int) -> None:
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


def _calibrate_send(
    interface: AudioInterface,
    freq: int,
    samplerate: int,
    level_dbfs: float,
) -> None:
    print("connect interface send to the voltmeter.")
    input("press enter to start send level calibration...")
    print("starting send level calibration...")
    stream = SineWaveStream(interface, freq, samplerate, level_dbfs)
    with stream:
        send_level_dbu = vrms_to_dbu(measure_acrms())
    interface.set_send_level_dbu(send_level_dbu, level_dbfs)
    interface.set_send_calibrated()
    print("send level calibration complete")
    print("recalibrate following any settings (gain) or hardware changes")


def _calibrate_returns(
    interface: AudioInterface,
    freq_start: int,
    freq_end: int,
    samplerate: int,
    level_dbfs: float,
    send_duration: float = 4.0,
) -> None:
    print("connect interface send to each return channel one at a time.")
    for i in range(interface.num_returns):
        input(f"press enter to start return level calibration for channel {i+1}...")
        print("starting return levels calibration...")
        stream = SineSweepStream(interface, freq_start, freq_end, send_duration, samplerate, level_dbfs)
        with stream:
            while not stream.done.wait(timeout=1.0):
                pass
        interface.set_return_level_dbu(level_dbfs, stream.get_return_levels()[i], i)
    interface.set_return_calibrated()
    print("return level calibration complete")
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


# def _process():
#     channel_delays, channel_inversions = calculate_latency(
#         stream.send_audio.unscaled_audio,
#         stream.return_audio,
#         stream.send_audio.samplerate,
#     )
#     processed_return_audio = process_recordings(
#         stream.send_audio.unscaled_audio,
#         stream.return_audio,
#         channel_delays,
#         channel_inversions,
#     )

#     if not no_show:
#         for i in range(interface.num_returns):
#             _plot_latency(
#                 i,
#                 stream.send_audio.samplerate,
#                 stream.send_audio.unscaled_audio,
#                 stream.return_audio,
#                 processed_return_audio,
#                 channel_delays,
#                 channel_inversions,
#             )

#     # Save the raw and processed recordings to two separate wav files
#     # The number of channels in the wav file is equal to the number of return channels
#     _write_wav(
#         Path(capture_dir, "recording-raw.wav"),
#         stream.return_audio,
#         stream.send_audio.samplerate,
#     )
#     _write_wav(
#         Path(capture_dir, f"recording-processed.wav"),
#         processed_return_audio,
#         stream.send_audio.samplerate,
#     )


def cli():
    parser = ArgumentParser(description="Capture tool")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("interfaces", help="List audio interfaces")

    interface_parser = subparsers.add_parser("interface", help="Show audio interface details")
    interface_parser.add_argument(
        "interface",
        nargs="?",
        type=int,
        default=None,
        help="interface id",
    )

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

    cal_send_parser = subparsers.add_parser("calibrate_send", help="calibrate send level")
    cal_send_parser.add_argument(
        "--level",
        type=float,
        default=DEFAULT_LEVEL_DBFS,
        help="output level in dBFS",
    )
    cal_send_parser.add_argument(
        "--freq",
        type=int,
        default=DEFAULT_FREQ,
        help="frequency in Hz",
    )
    cal_send_parser.add_argument(
        "--samplerate",
        type=int,
        default=DEFAULT_SAMPLERATE,
        help="samplerate in Hz",
    )

    cal_return_parser = subparsers.add_parser("calibrate_return", help="calibrate return level")
    cal_return_parser.add_argument(
        "--level",
        type=float,
        default=DEFAULT_LEVEL_DBFS,
        help="output level in dBFS",
    )
    cal_return_parser.add_argument(
        "--freq_start",
        type=int,
        default=DEFAULT_FREQ_SWEEP_START,
        help="start frequency in Hz",
    )
    cal_return_parser.add_argument(
        "--freq_end",
        type=int,
        default=DEFAULT_FREQ_SWEEP_END,
        help="end frequency in Hz",
    )
    cal_return_parser.add_argument(
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

    args = parser.parse_args()

    db = ForgeDB()
    interface_config = db.get_interface()
    if args.command == "interfaces":
        _print_interfaces()
    elif args.command == "interface":
        device = args.interface if args.interface else interface_config["device"]
        _print_interface(device)
    else:
        interface = AudioInterface(interface_config)

        if args.command == "calibrate_send":
            _calibrate_send(interface, args.freq, args.samplerate, args.level)
            db.set_interface(interface.get_config())
        elif args.command == "calibrate_return":
            _calibrate_returns(interface, args.freq_start, args.freq_end, args.samplerate, args.level)
            db.set_interface(interface.get_config())
        elif args.command == "tone":
            if args.level_dbu is not None:
                level_dbfs = interface.send_dbu_to_dbfs(args.level_dbu)
            else:
                level_dbfs = args.level

            stream = SineWaveStream(interface, args.frequency, args.samplerate, level_dbfs)
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
        elif args.command == "run":
            manifest_path = Path(args.manifest)
            manifest = CaptureManifest(manifest_path)
            stream = CaptureStream(interface, manifest.input_data, manifest.samplerate, manifest.level_dbu)

            print("verify interface send and returns are connected to the device to be modeled")
            input("press enter to start capture...")
            try:
                with stream:
                    output_str = " | ".join(f"{dbu:3.2f}" for dbu in stream.get_return_levels())
                    print(
                        f"{stream.send_audio.get_time()} / {stream.send_audio.get_duration()} - {output_str}          "
                    )
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
