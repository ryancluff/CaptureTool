from argparse import ArgumentParser

from core.db import ForgeDB
from core.audio import vrms_to_dbu
from core.interface import AudioInterface
from core.stream import SineWaveStream, SineSweepStream
from calibration.voltmeter import measure_acrms


DEFAULT_FREQ = 1000  # Hz
DEFAULT_FREQ_SWEEP_START = 20  # Hz
DEFAULT_FREQ_SWEEP_END = 20000  # Hz
DEFAULT_SAMPLERATE = 48000  # Hz
DEFAULT_LEVEL_DBFS = -3.0  # dBFS


def _setup_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Forge Calibration CLI")
    subparsers = parser.add_subparsers(dest="calibration_type")

    send_parser = subparsers.add_parser("send", help="calibrate send level")
    send_parser.add_argument(
        "--level",
        type=float,
        default=DEFAULT_LEVEL_DBFS,
        help="output level in dBFS",
    )
    send_parser.add_argument(
        "--freq",
        type=int,
        default=DEFAULT_FREQ,
        help="frequency in Hz",
    )
    send_parser.add_argument(
        "--samplerate",
        type=int,
        default=DEFAULT_SAMPLERATE,
        help="samplerate in Hz",
    )

    return_parser = subparsers.add_parser("return", help="calibrate return level")
    return_parser.add_argument(
        "--level",
        type=float,
        default=DEFAULT_LEVEL_DBFS,
        help="output level in dBFS",
    )
    return_parser.add_argument(
        "--freq_start",
        type=int,
        default=DEFAULT_FREQ_SWEEP_START,
        help="start frequency in Hz",
    )
    return_parser.add_argument(
        "--freq_end",
        type=int,
        default=DEFAULT_FREQ_SWEEP_END,
        help="end frequency in Hz",
    )
    return_parser.add_argument(
        "--sweep_duration",
        type=float,
        default=4.0,
        help="duration of the sweep in seconds",
    )
    return_parser.add_argument(
        "--samplerate",
        type=int,
        default=DEFAULT_SAMPLERATE,
        help="samplerate in Hz",
    )

    return parser


def main():
    parser = _setup_parser()
    args = parser.parse_args()
    calibration_type: str = args.calibration_type
    samplerate: int = args.samplerate
    level_dbfs: float = args.level

    db = ForgeDB()
    interface_config = db.get_interface()
    interface = AudioInterface(interface_config)

    if calibration_type == "send":
        freq: int = args.freq

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
        db.set_interface(interface.get_config())

    elif calibration_type == "return":
        freq_start: int = args.freq_start
        freq_end: int = args.freq_end
        sweep_duration: float = args.sweep_duration

        print("connect interface send to each return channel one at a time.")
        for i in range(interface.num_returns):
            input(f"press enter to start return level calibration for channel {i+1}...")
            print("starting return levels calibration...")
            stream = SineSweepStream(interface, freq_start, freq_end, sweep_duration, samplerate, level_dbfs)
            with stream:
                while not stream.done.wait(timeout=1.0):
                    pass
            interface.set_return_level_dbu(level_dbfs, stream.get_return_levels()[i], i)
        interface.set_return_calibrated()
        print("return level calibration complete")
        print("recalibrate following any settings (gain) or hardware changes")

        db.set_interface(interface.get_config())
