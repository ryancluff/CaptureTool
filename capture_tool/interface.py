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
    def __init__(self, config: dict):
        # Interface configuration
        self.device = config.get("device", sd.default.device)
        self.channels = config.get("channels", {})
        self.num_output_channels = self.channels["reamp"]
        self.num_input_channels = len(self.channels["input"])

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

    def calibrate_reamp(
        self,
        init_dbfs=0.0,
    ):
        num_output_channels = self.channels["reamp"]
        num_input_channels = len(self.channels["input"])

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
            reamp_v_rms = float(input(f"enter measured rms voltage: "))
            reamp_dbu = v_rms_to_dbu(reamp_v_rms)
            self.reamp_delta = reamp_dbu - init_dbfs
            target_dbfs = dbu_to_dbfs(self.target_dbu, self.reamp_delta)

            while reamp_dbu - self.target_dbu > 0.001:
                sine_wave = SineWave(self.frequency, self.samplerate, target_dbfs)
                reamp_v_rms = float(input("enter new rms voltage: "))
                reamp_dbu = v_rms_to_dbu(reamp_v_rms)
                self.reamp_delta = reamp_dbu - init_dbfs
                target_dbfs = dbu_to_dbfs(self.target_dbu, self.reamp_delta)

        return self.reamp_delta
