import sys
import threading
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
        self.input_deltas = config.get("input_deltas", None)

    def calibrate_reamp(
        self,
        init_dbfs=0.0,
    ) -> float:
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

    def calibrate_inputs(
        self,
        test_dbfs: float = 0.0,
    ) -> list[float]:
        self.input_deltas = [0.0] * self.num_input_channels

        sine_wave = SineWave(self.frequency, self.samplerate, test_dbfs)
        sine_wave_2s = np.zeros(2 * self.samplerate)
        for i in range(len(sine_wave_2s)):
            sine_wave_2s[i] = next(sine_wave)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal recording_levels
            nonlocal current_frame
            chunksize = min(len(sine_wave_2s) - current_frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_output_channels))
            output[:chunksize, self.channels["reamp"] - 1] = sine_wave_2s[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            # read the recording data from the interface input channels
            input = unpack(indata, self.num_input_channels)
            recording_levels[:] = np.max(np.abs(input), axis=0)

            current_frame += frames
            if current_frame >= len(sine_wave_2s):
                raise sd.CallbackStop()

        for i in range(self.num_input_channels):
            current_frame = 0
            recording_levels = np.zeros(self.num_input_channels, dtype=np.int32)
            recording_done = threading.Event()
            stream = sd.RawStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                device=self.device,
                channels=(self.num_input_channels, self.num_output_channels),
                dtype="int24",
                callback=callback,
                finished_callback=recording_done.set,
            )
            input(f"channel {i} - press enter to continue")
            with stream:
                while not recording_done.wait(timeout=1.0):
                    pass
            self.input_deltas[i] = int_to_dbfs(recording_levels[i]) - test_dbfs

        return self.input_deltas

    def passthrough(self):
        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            outdata[:] = indata

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_input_channels, self.num_output_channels),
            dtype="int24",
            callback=callback,
        )

        with stream:
            time.sleep(duration)