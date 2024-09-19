import sys
import math

import numpy as np
import sounddevice as sd

from util import SineWave, pack


def run():
    device_index = 6
    samplerate = 96000

    chunk = 960

    frequency = 1000

    out_channel = 3  # 1-based index
    out_channels = 4

    sine_wave = SineWave(frequency, samplerate, 0)

    try:
        # Define callback for playback
        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            output = np.zeros((frames, out_channels))
            for i in range(frames):
                output[i, out_channel - 1] = next(sine_wave)
            outdata[:] = pack(output.flatten())

        stream = sd.RawOutputStream(
            samplerate=samplerate,
            blocksize=chunk,
            device=device_index,
            channels=out_channels,
            dtype="int24",
            callback=callback,
        )

        with stream:
            reamp_v_rms = input("Enter reamp rms Voltage: ")
            reamp_dbu = 20 * math.log10(float(reamp_v_rms) / 0.7746)
            dbfs = 12 - reamp_dbu
            sine_wave = SineWave(frequency, samplerate, dbfs)

            reamp_v_rms = input("Enter new reamp rms Voltage: ")
            reamp_dbu = 20 * math.log10(float(reamp_v_rms) / 0.7746)

            print("Output gain (dBu): ", reamp_dbu)
            print("ReAMP gain (dBFS): ", dbfs)
            if reamp_dbu < 12.01 and reamp_dbu > 11.99:
                print("Calibration successful")
            else:
                print("Calibration failed")

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
