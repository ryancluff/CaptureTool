import sys
import time

import numpy as np
import sounddevice as sd

from util import SineWave, pack, unpack, v_rms_to_dbu, calculate_channel_dbfs


def calibrate(
    device: int,
    output_channel: int,
    input_channels: list,
    target_dbu: float,
    frequency: int = 1000,
    blocksize: int = 480,
    samplerate: int = 48000,
):
    sine_wave = SineWave(frequency, samplerate, 0)
    input_max = np.zeros(len(input_channels), dtype=np.int32)

    def callback(indata, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        output = np.zeros((frames, output_channel), dtype=np.int32)
        for i in range(frames):
            output[i, output_channel - 1] = next(sine_wave)
        outdata[:] = pack(output)

        input = unpack(indata, len(input_channels))

        nonlocal input_max
        input_max[:] = np.max(np.abs(input), axis=0)

    stream = sd.RawStream(
        samplerate=samplerate,
        blocksize=blocksize,
        device=device,
        channels=(len(input_channels), output_channel),
        dtype="int24",
        callback=callback,
    )

    with stream:
        reamp_v_rms = float(input(f"Enter RMS voltage: "))
        # reamp_v_rms = 3.424
        reamp_dbu = v_rms_to_dbu(reamp_v_rms)

        if reamp_dbu < target_dbu:
            print("Reamp gain too low, increase output level or decrease reamp pad")
            return

        output_level = target_dbu - reamp_dbu

        sine_wave = SineWave(frequency, samplerate, output_level)
        reamp_v_rms_verify = float(input("Enter new RMS voltage: "))
        # reamp_v_rms_verify = 3.084
        reamp_dbu_verify = v_rms_to_dbu(reamp_v_rms_verify)

        print(f"reamp target level: {target_dbu:.2f} dBu")
        print(f"measured reamp level @ 0 dBFS: {reamp_dbu:.2f} dBu")
        print(f"calculated reamp level adjustment: {output_level:.2f} dB")
        print(f"measured reamp level @ {output_level:.2f} dB: {reamp_dbu_verify:.2f} dBu")
        print("")

        print("Verify reamp input and output levels. Press Ctrl+C to exit.")
        print("")

        try:
            while True:
                input_dbfs = calculate_channel_dbfs(input_max)
                output_str = " | ".join(f"{dbu:.2f}" for dbu in input_dbfs)
                print(f"dBFS: {output_str}")
                time.sleep(1)
        except KeyboardInterrupt:
            print("")

        return output_level


if __name__ == "__main__":
    calibrate(6, 3, ["source", "preamp", "poweramp", "di"], 6.0)
