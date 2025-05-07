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
from capture_tool.interface import AudioInterface
from capture_tool.util import timestamp


def _print_interfaces() -> None:
    print(sd.query_devices())


def _print_interface(device: int) -> None:
    if device == -1:
        device = sd.default.device
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


def _read_config(path: Path) -> dict:
    with open(path, "r") as fp:
        config = json.load(fp)
        config["config_path"] = str(path)
    return config


def _write_config(
    capture_dir: Path,
    config: dict,
    name: str = "config",
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


def _write_wav(path: Path, data: np.array, samplerate: int) -> None:
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
    if interface._send_level_dbu is None:
        print("send level calibration required. verify interface send is only connect to the voltmeter.")
        input("press enter to start send level calibration...")
        print("starting send level calibration...")
        stream = interface.get_send_calibration_stream(send_level_dbfs=send_level_dbfs)
        with stream:
            send_level_dbu = v_rms_to_dbu(float(input(f"enter measured rms voltage: ")))
        interface.set_send_level_dbu(send_level_dbu, send_level_dbfs)
        print("send level calibration complete")
        print("calibration value saved to config in capture directory")
        print("copy the following values to the supplied config file to skip calibration in the future")
    else:
        print("send level calibration not required")
        print("the following values were supplied config file, skipping calibration")
    print(f'"_send_level_dbu ": {interface._send_level_dbu:f}')
    print("recalibrate following any settings (gain) or hardware changes")


def _calibrate_returns(
    interface: AudioInterface,
    send_level_dbfs: float = -3.0,
) -> None:
    if interface._return_levels_dbu is None:
        print("return level calibration required. connect the send output to each return channel one at a time")
        input("press enter to start return level calibration...")
        print("starting return levels calibration...")
        for i in range(interface.num_returns):
            input(f"channel {i + 1} - press enter to continue")
            clip = True
            while clip:
                stream, levels, done = interface.get_return_calibration_stream(send_level_dbfs=send_level_dbfs)
                with stream:
                    while not done.wait(timeout=1.0):
                        pass
                interface.set_return_level_dbu(
                    interface.send_dbfs_to_dbu(send_level_dbfs),
                    int_to_dbfs(levels[i]),
                    i,
                )
        print("return level calibration complete")
        print("send level calibration complete")
        print("calibration value saved to config in capture directory")
        print("copy the following values to the supplied config file to skip calibration in the future")
    else:
        print("return level calibration not required")
        print("the following values were supplied config file, skipping calibration")
    print(f'"_return_levels_dbu ": {interface._return_levels_dbu:f}')
    print("recalibrate following any settings (gain) or hardware changes")


def _plot_latency(
    channel: int,
    samplerate: int,
    send_audio: np.array,
    return_audio: np.array,
    processed_return_audio: np.array,
    channel_delays: np.array,
    channel_inversions: np.array,
) -> None:
    samples = samplerate * 5
    plt.figure(figsize=(16, 5))
    plt.plot(
        send_audio[:samples] / np.max(send_audio[:samples]),
        label="reamp",
    )
    plt.plot(
        return_audio[:samples, channel] / np.max(return_audio[:samples, channel]),
        linestyle="--",
        label="raw recording",
    )
    plt.plot(
        processed_return_audio[:samples, channel] / np.max(processed_return_audio[:samples, channel]),
        linestyle="-.",
        label="processed recording",
    )
    plt.title(
        f"channel={channel} | base delay={channel_delays[0]} | channel_delay={channel_delays[channel]} | invert={channel_inversions[channel]}"
    )
    plt.legend()
    plt.show(block=True)


def _test_tone(interface: AudioInterface, unit: AudioInterface.TestToneUnit, level: float) -> None:
    if unit == AudioInterface.TestToneUnit.DBFS:
        if level is None:
            level = -3
    elif unit == AudioInterface.TestToneUnit.DBU:
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
            print(
                "output level: ",
                get_output_level_dbfs(),
                " dbfs" if unit == AudioInterface.TestToneUnit.DBFS else "dbu",
            )
            if control == "1":
                increase_output_level()
            elif control == "2":
                decrease_output_level()
            elif control == "0" or control == "q":
                pass
            else:
                print("invalid input")
            control = input("> ")


def _capture(config_path: Path, no_show: bool = False) -> None:
    config = _read_config(config_path)
    interface = AudioInterface(config)
    captures_dir = _create_captures_dir()
    capture_dir = _create_capture_dir(captures_dir)

    # calibrate interface send level
    _calibrate_send(interface, send_level_dbfs=-3.0)
    _write_config(capture_dir, interface.get_config())

    print("verify interface send and returns are connected to the device to be modeled")
    stream, get_frame, send_audio, return_audio, peak_levels, done = interface.get_capture_stream()
    complete = False
    while not complete:
        input("press enter to start capture...")
        try:
            with stream:
                while not done.wait(timeout=1.0):
                    peak_dbfs = int_to_dbfs(peak_levels)
                    for i in range(interface.num_returns):
                        if peak_dbfs[i] > 0:
                            raise AudioInterface.ClipException(i + 1, peak_dbfs[i])
                    output_str = " | ".join(f"{dbu:3.2f}" for dbu in peak_dbfs)
                    current_seconds = get_frame() // interface.wav.rate
                    current_seconds = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
                    total_seconds = len(interface.wav.data) // interface.wav.rate
                    total_seconds = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
                    print(f"{current_seconds} / {total_seconds} - {output_str}          ")
            complete = True
        except AudioInterface.ClipException as e:
            print(e.message)
            print(f"decrease the return level gain on channel {e.channel} and restart capture")
            stream, get_frame, send_audio, return_audio, peak_levels, done = interface.get_capture_stream()
        except KeyboardInterrupt:
            print(f"capture manually stopped at {current_seconds} / {total_seconds}")
            complete = True

    channel_delays, channel_inversions = calculate_latency(
        send_audio,
        return_audio,
        interface.samplerate,
    )
    processed_return_audio = process_recordings(
        send_audio,
        return_audio,
        channel_delays,
        channel_inversions,
    )

    if not no_show:
        for i in range(interface.num_returns):
            _plot_latency(
                i,
                interface.samplerate,
                send_audio,
                return_audio,
                processed_return_audio,
                channel_delays,
                channel_inversions,
            )

    # Save the raw recording to a single wav file
    # The number of channels in the wav file is equal to the number of return channels
    _write_wav(
        Path(capture_dir, "recording-raw.wav"),
        return_audio,
        interface.wav.rate,
    )

    # Save the processed recording data
    # Each channel is saved to a separate mono wav file
    for i in range(interface.num_returns):
        channel = interface.channels["returns"][i]
        _write_wav(
            Path(capture_dir, f"recording-{channel}.wav"),
            processed_return_audio[:, i],
            interface.wav.rate,
        )

    # Calibrate interface return levels
    _calibrate_returns(interface, send_level_dbfs=-3.0)
    _write_config(capture_dir, interface.get_config())


def cli():
    parser = ArgumentParser(description="Capture tool")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("interfaces", help="List audio interfaces")
    interface_parser = subparsers.add_parser("interface")
    interface_parser.add_argument("interface", nargs="?", type=int, default=-1, help="interface id")

    testtone_parser = subparsers.add_parser("testtone", help="Generate a test tone")
    testtone_parser.add_argument("interface_config_path", type=str)
    testtone_parser.add_argument("type", nargs="?", type=str, default="dbfs", choices=["dbfs", "dbu"])
    testtone_parser.add_argument("--level", type=float, required=False)

    capture_parser = subparsers.add_parser("run", help="Run a capture")
    capture_parser.add_argument("capture_path", type=str)
    capture_parser.add_argument("--no-show", action="store_true", help="Skip plotting latency info")

    args = parser.parse_args()

    if args.command == "interfaces":
        _print_interfaces()
    elif args.command == "interface":
        _print_interface(args.interface)
    elif args.command == "testtone":
        interface_config = _read_config(args.interface_config_path)
        interface = AudioInterface(interface_config)
        _test_tone(interface, args.type, args.level)
    elif args.command == "run":
        forge_dir, session_dir, capture_dir = Path(args.capture_path).parts
        interface_config = _read_config(Path(forge_dir, "interface.json"))
        selected_config = _read_config(Path(forge_dir, "selected.json"))
        session_config = _read_config(Path(forge_dir, session_dir, "session.json"))
        capture_config = _read_config(Path(forge_dir, session_dir, capture_dir, "capture.json"))
        interface = AudioInterface(interface_config)
        _capture(args.capture_config_path, no_show=args.no_show)


if __name__ == "__main__":
    cli()
