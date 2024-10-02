import argparse
import json

from src.capture import capture
from src.calibrate import calibrate
import settings


def main():

    output_level = calibrate(
        settings.device,
        settings.output_channel,
        settings.input_channels,
        settings.target_dbu,
        frequency=settings.frequency,
        blocksize=settings.calibration_blocksize,
        samplerate=settings.calibration_samplerate,
    )

    capture(
        settings.device,
        settings.output_channel,
        settings.input_channels,
        settings.reamp_file,
        output_level,
        blocksize=settings.capture_blocksize,
    )

    print("Capture complete")


if __name__ == "__main__":
    main()
