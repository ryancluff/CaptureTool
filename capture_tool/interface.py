import sys
import time

import numpy as np
import sounddevice as sd

from util import SineWave, pack, unpack, v_rms_to_dbu, calculate_channel_dbfs


class Interface:
    def __init__(self, config: dict):
        # Interface configuration
        self.device = config["device"]
        self.output_channel = config["output_channel"]
        self.input_channels = config["input_channels"]

        # Interface calibration settings
        self.target_dbu = config["target_dbu"]
        self.frequency = config["frequency"]
        self.blocksize = config["calibration_blocksize"]
        self.samplerate = config["calibration_samplerate"]

        # Interface calibration results
        self.output_level = None

    def calibrate(self):
        sine_wave = SineWave(self.frequency, self.samplerate, 0)
        input_max = np.zeros(len(self.input_channels), dtype=np.int32)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            output = np.zeros((frames, self.output_channel), dtype=np.int32)
            for i in range(frames):
                output[i, self.output_channel - 1] = next(sine_wave)
            outdata[:] = pack(output)

            input = unpack(indata, len(self.input_channels))

            nonlocal input_max
            input_max[:] = np.max(np.abs(input), axis=0)

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(len(self.input_channels), self.output_channel),
            dtype="int24",
            callback=callback,
        )

        with stream:
            reamp_v_rms = float(input(f"Enter RMS voltage: "))
            # reamp_v_rms = 3.424
            reamp_dbu = v_rms_to_dbu(reamp_v_rms)

            if reamp_dbu < self.target_dbu:
                print("Reamp gain too low, increase output level or decrease reamp pad")
                return

            output_level = self.target_dbu - reamp_dbu

            sine_wave = SineWave(self.frequency, self.samplerate, output_level)
            reamp_v_rms_verify = float(input("Enter new RMS voltage: "))
            # reamp_v_rms_verify = 3.084
            reamp_dbu_verify = v_rms_to_dbu(reamp_v_rms_verify)

            print(f"reamp target level: {self.target_dbu:.2f} dBu")
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

        self.output_level = output_level

if __name__ == "__main__":
    interface = Interface(
        {
            "device": 6,
            "output_channel": 3,
            "input_channels": ["source", "preamp", "poweramp", "di"],
            "target_dbu": 6.0,
            "frequency": 1000,
            "calibration_blocksize": 1024,
            "calibration_samplerate": 48000,
        }
    )
    interface.calibrate()
