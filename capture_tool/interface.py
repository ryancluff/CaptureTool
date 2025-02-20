import sys
import time

import numpy as np
import sounddevice as sd

from capture_tool.audio import (
    SineWave,
    pack,
    unpack,
    v_rms_to_dbu,
    dbu_to_dbfs,
    dbfs_to_dbu,
    int_to_dbfs,
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

        if self.reamp_delta is not None and not isinstance(self.reamp_delta, float):
            if isinstance(self.reamp_delta, int):
                self.reamp_delta = float(self.reamp_delta)
            else:
                raise ValueError("reamp_delta must be a number")
        if self.input_delta is not None and not isinstance(self.input_delta, float):
            if isinstance(self.input_delta, int):
                self.input_delta = float(self.input_delta)
            else:
                raise ValueError("passthrough_delta must be a number")

    def __init__(self, config: dict):
        # Interface configuration
        self.device = config.get("device", sd.default.device)
        self.channels = config.get("channels", {})

        # Interface settings
        self.samplerate = config.get("samplerate", sd.default.samplerate)
        self.blocksize = config.get("blocksize", 256)

        # Calibration settings
        self.target_dbu = config.get("target_dbu", 6.0)
        self.frequency = config.get("frequency", 1000)

        # Interface calibration results
        # dB adjustments for dBu to dBFS conversion
        # (dbu - dbfs = delta)
        self.reamp_delta = config.get("reamp_delta", None)
        self.input_delta = config.get("passthrough_delta", None)

        self._validate_config()

    def passthrough(self):
        if self.reamp_delta is None:
            raise RuntimeError("Interface not calibrated")

        num_output_channels = max(self.channels["reamp"], self.channels["monitor"])
        num_input_channels = len(self.channels["input"])

        output_channel = self.channels["reamp"]
        passthrough_channel = None
        for i in self.channels["input"]:
            if i == self.channels["passthrough"]:
                passthrough_channel = i
                break
        if passthrough_channel is None:
            raise ValueError("passthrough channel not found in input channels")

        output_scalar = 10 ** (self.reamp_delta - self.input_delta[passthrough_channel - 1] / 20.0)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal output_channel
            input = unpack(indata, num_input_channels)
            output = np.zeros((frames, num_output_channels), dtype=np.int32)
            output[:, output_channel] = np.multiply(input[:, passthrough_channel - 1], output_scalar)
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

        init_dbfs = 0
        sine_wave = SineWave(self.frequency, self.samplerate, init_dbfs)
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

            reamp_v_rms = float(input(f"enter measured rms voltage: "))
            reamp_dbu = v_rms_to_dbu(reamp_v_rms)
            self.reamp_delta = reamp_dbu - init_dbfs
            target_dbfs = dbu_to_dbfs(self.target_dbu, self.reamp_delta)
            sine_wave = SineWave(self.frequency, self.samplerate, target_dbfs)

            reamp_v_rms_verify = float(input("enter new rms voltage: "))
            reamp_dbu_verify = v_rms_to_dbu(reamp_v_rms_verify)
            reamp_dbfs_verify = dbu_to_dbfs(reamp_dbu_verify, self.reamp_delta)

            print("")
            print(f"target reamp level: {self.target_dbu:.2f} dBu")
            print(f"measured reamp level @ {init_dbfs:.2f} dBFS: {reamp_dbu:.2f} dBu")
            print(f"measured reamp level @ {target_dbfs:.2f} dBFS: {reamp_dbu_verify:.2f} dBu")
            print(f"calculated input delta (dbu - dbfs): {self.reamp_delta:.2f}")
            print("")

            print("verify reamp output and set input levels")
            print()
            print("press Ctrl+C to exit")
            print("")

            try:
                while True:
                    input_dbfs = int_to_dbfs(input_max)
                    input_dbu = dbfs_to_dbu(input_dbfs, self.reamp_delta)
                    input_dbfs_str = " | ".join(f"{i:3.2f}" for i in input_dbfs)
                    input_dbu_str = " | ".join(f"{i:3.2f}" for i in input_dbu)
                    print(f"  dBFS: {input_dbfs_str} || dBu: {input_dbu_str}        ", end="\r")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("")

        self.input_delta = input_dbfs - reamp_dbfs_verify

        print("calibration complete")
        print("add the following lines to your interface config to skip calibration")
        print("")
        print(f'"reamp_delta": {self.reamp_delta:.2f},')
        print(f'"input_delta": [{", ".join(f"{i:.2f}" for i in self.input_delta)}],')

        print("recalibrate following any setting or hardware changes")
        print("")

        return self.reamp_delta, self.input_delta.tolist()
