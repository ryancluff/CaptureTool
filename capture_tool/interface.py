import sys
import time

import numpy as np
import sounddevice as sd

from capture_tool.audio import (
    SineWave,
    pack,
    unpack,
    v_rms_to_dbu,
    calculate_channel_dbfs,
)


class Interface:
    # TODO: Add more validation stuff
    def _validate_config(self):
        if not isinstance(self.device, int):
            raise ValueError("device must be an integer")
        if not isinstance(self.channels, dict):
            raise ValueError("channels must be a dictionary")

        if not isinstance(self.target_dbu, float):
            if isinstance(self.target_dbu, int):
                self.target_dbu = float(self.target_dbu)
            else:
                raise ValueError("target_dbu must be a number")
        if not isinstance(self.frequency, int):
            raise ValueError("frequency must be an integer")
        if not isinstance(self.samplerate, int):
            raise ValueError("samplerate must be an integer")
        if not isinstance(self.blocksize, int):
            raise ValueError("blocksize must be an integer")

        if self.reamp_dbu is not None and not isinstance(self.reamp_dbu, float):
            if isinstance(self.reamp_dbu, int):
                self.reamp_dbu = float(self.reamp_dbu)
            else:
                raise ValueError("output_level must be a number")

    def __init__(self, config: dict):
        # Interface configuration
        self.device = config.get("device", sd.default.device)
        self.channels = config.get("channels", {})

        # Interface calibration settings
        self.target_dbu = config.get("target_dbu", 6.0)
        self.frequency = config.get("frequency", 1000)
        self.samplerate = config.get("samplerate", sd.default.samplerate)
        self.blocksize = config.get("blocksize", 256)

        # Interface calibration results
        # reamp dBu measure at 0 dBFS
        self.reamp_dbu = config.get("reamp_dbu", None)

        self._validate_config()

    def passthrough(self):
        if self.reamp_dbu is None:
            raise RuntimeError("Interface not calibrated")

        num_output_channels = max(self.channels["reamp"], self.channels["monitor"])
        num_input_channels = len(self.channels["input"])

        output_channel = self.channels["reamp"]

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal output_channel
            input = unpack(indata, num_input_channels)
            output = np.zeros((frames, num_output_channels), dtype=np.int32)
            output[:, output_channel] = input[:, self.channels("passthrough") - 1]
            outdata[:] = pack(output)

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(num_input_channels, num_output_channels),
            dtype="int24",
            callback=callback,
        )

        with stream:
            print("Passthrough mode")
            print("=" * 80)
            print("")

            user_input = ""
            while user_input != "q":
                user_input = input("enter 1 for reamp, 2 for monitor, or 'q' to quit: ")
                if user_input == "1":
                    output_channel = self.channels["reamp"]
                elif user_input == "2":
                    output_channel = self.channels["monitor"]

    def calibrate(self):
        num_output_channels = self.channels["reamp"]
        num_input_channels = len(self.channels["input"])

        sine_wave = SineWave(self.frequency, self.samplerate, 0)
        input_max = np.zeros(num_input_channels, dtype=np.int32)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            output = np.zeros((frames, num_output_channels), dtype=np.int32)
            for i in range(frames):
                output[i, self.channels["reamp"] - 1] = next(sine_wave)
            outdata[:] = pack(output)

            input = unpack(indata, num_input_channels)

            nonlocal input_max
            input_max[:] = np.max(np.abs(input), axis=0)

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(num_input_channels, num_output_channels),
            dtype="int24",
            callback=callback,
        )

        with stream:
            print("Calibration Mode")
            print("=" * 80)
            print("")

            reamp_v_rms = float(input(f"enter rms voltage: "))
            self.reamp_dbu = v_rms_to_dbu(reamp_v_rms)

            reamp_dbfs = self.target_dbu - self.reamp_dbu
            sine_wave = SineWave(self.frequency, self.samplerate, reamp_dbfs)
            reamp_v_rms_verify = float(input("enter new rms voltage: "))
            reamp_dbu_verify = v_rms_to_dbu(reamp_v_rms_verify)

            print("")
            print(f"reamp target level: {self.target_dbu:.2f} dBu")
            print(f"measured reamp level @ 0 dBFS: {self.reamp_dbu:.2f} dBu")
            print(f"calculated reamp level adjustment: {reamp_dbfs:.2f} dBFS")
            print(f"measured reamp level @ {reamp_dbfs:.2f} dBFS: {reamp_dbu_verify:.2f} dBu")
            print("")

            print("verify reamp output and set input levels")
            print()
            print("press Ctrl+C to exit")
            print("")

            try:
                while True:
                    input_dbfs = calculate_channel_dbfs(input_max)
                    output_str = " | ".join(f"{dbu:3.2f}" for dbu in input_dbfs)
                    print(f"dBFS: {output_str}", end="\r")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("")

        print("calibration complete")
        print("add the following lines to your interface config to skip calibration")
        print("")
        print(f'"reamp_dbu": {self.reamp_dbu:.2f},')
        print(f'"input_dbfs": []')

        print("recalibrate following any setting or hardware changes")
        print("")
