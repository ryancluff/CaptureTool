from enum import Enum
import sys
import threading
import time

import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import wavio

from capture_tool.audio import (
    SineWave,
    pack,
    unpack,
    v_rms_to_dbu,
    db_to_scalar,
    dbu_to_dbfs,
    dbfs_to_dbu,
    int_to_dbfs,
)

LATENCY_OFFSET = 0


class LatencyAdjustment(Enum):
    NONE = 0
    BASE = 1
    INDIVIDUAL = 2


class TestToneUnit(Enum):
    DBFS = 0
    DBU = 1


class AudioInterface:
    def __init__(self, config: dict):
        self.input_wav = wavio.read(config["reamp_file"])
        self.send_level_dbu = config["reamp_level_dbu"]

        # Interface configuration
        self.device = config.get("device", sd.default.device)
        self.samplerate = config.get("samplerate", self.input_wav.rate)
        self.blocksize = config.get("blocksize", 256)
        self.channels = config.get("channels", {})
        self.num_output_channels = self.channels["reamp"]
        self.num_input_channels = len(self.channels["input"])

        # Calibration settings
        self.output_level_max_dbu = config.get("output_level_max_dbu", 6.0)
        self.frequency = config.get("frequency", 1000)

        # Interface calibration results
        # dB adjustments for dBu to dBFS conversion
        # (dbu - dbfs = delta)

        # Optional calibration values
        # The level (dBu) being sent from the interface to the gear corresponding to a 1kHz sine wave with 0dBFS peak
        self._send_level_dbu = config.get("_send_level_dbu ", None)
        # The level (dBu) returned from the device to the interface corresponding to a 1kHz sine wave with 0dBFS peak
        self._return_level_dbu = config.get("_return_level_dbu", None)

    def calibrate_reamp(
        self,
        init_dbfs: float = -3.0,
    ) -> float:
        sine_wave = SineWave(self.frequency, self.samplerate, init_dbfs)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            output = np.zeros((frames, self.num_output_channels), dtype=np.int32)
            for i in range(frames):
                output[i, self.channels["reamp"] - 1] = next(sine_wave)
            outdata[:] = pack(output)

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_input_channels, self.num_output_channels),
            dtype="int24",
            callback=callback,
        )

        with stream:
            reamp_v_rms = float(input(f"enter measured rms voltage: "))
            reamp_dbu = v_rms_to_dbu(reamp_v_rms)
            self._send_level_dbu = reamp_dbu - init_dbfs
            target_dbfs = dbu_to_dbfs(self.output_level_max_dbu, self._send_level_dbu)

            while reamp_dbu - self.output_level_max_dbu > 0.001:
                sine_wave = SineWave(self.frequency, self.samplerate, target_dbfs)
                reamp_v_rms = float(input("enter new rms voltage: "))
                reamp_dbu = v_rms_to_dbu(reamp_v_rms)
                self._send_level_dbu = reamp_dbu - init_dbfs
                target_dbfs = dbu_to_dbfs(self.output_level_max_dbu, self._send_level_dbu)

        return self._send_level_dbu

    def calibrate_inputs(
        self,
        test_dbfs: float = 0.0,
    ) -> list[float]:
        self._return_level_dbu = [0.0] * self.num_input_channels

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
            self._return_level_dbu[i] = int_to_dbfs(recording_levels[i]) - test_dbfs

        return self._return_level_dbu

    def _calculate_latency(
        self,
        reamp_data: np.ndarray,
        raw_recording: np.ndarray,
        cc_len: int = 5,
    ) -> tuple[np.ndarray, np.ndarray]:
        channel_delays = np.zeros(self.num_input_channels, dtype=np.int32)
        channel_inversions = np.zeros(self.num_input_channels, dtype=np.bool)

        # trim input and output data for cross correlation
        reamp_short = reamp_data[: self.input_wav.rate * cc_len, 0]
        recording_short = raw_recording[: self.input_wav.rate * cc_len, :]

        # normalize data to -1 to 1 to prevent overflow in cross correlation
        reamp_short = reamp_short / np.max(np.abs(reamp_short))
        for i in range(self.num_input_channels):
            output_data_short_normalized = recording_short[:, i] / np.max(np.abs(recording_short[:, i]))

            # calculate cross correlation for each channel
            # if the maximum cross correlation is negative, invert the channel
            cross_corr = np.correlate(reamp_short, output_data_short_normalized, mode="full")
            max_cc = np.argmax(cross_corr)
            min_cc = np.argmin(cross_corr)
            if np.abs(cross_corr[max_cc]) < np.abs(cross_corr[min_cc]):
                max_cc = min_cc
                channel_inversions[i] = True

            # Calculate the delay for each channel
            channel_delays[i] = len(recording_short) - max_cc - 1 - LATENCY_OFFSET
        return channel_delays, channel_inversions

    def _process_recordings(
        self,
        reamp_audio: np.ndarray,
        raw_recording: np.ndarray,
        channel_delays: np.ndarray,
        channel_inversions: np.ndarray,
        latency_adjustment: LatencyAdjustment = LatencyAdjustment.BASE,
        inversion_adjustment: bool = True,
    ) -> np.ndarray:
        processed_recording = np.zeros_like(raw_recording)

        # apply the calculated delays to the recording data
        if latency_adjustment == LatencyAdjustment.BASE:
            for i in range(self.num_input_channels):
                processed_recording[: -channel_delays[i], i] = raw_recording[channel_delays[i] :, i]
        elif latency_adjustment == LatencyAdjustment.INDIVIDUAL:
            for i in range(self.num_input_channels):
                processed_recording[: -channel_delays[0], i] = raw_recording[channel_delays[0] :, i]
        else:
            processed_recording[:, :] = raw_recording[:, :]

        # invert the recording data if necessary
        if inversion_adjustment:
            for i in range(self.num_input_channels):
                if channel_inversions[i]:
                    print(f"detected signal inversion on channel {i}, correcting")
                    processed_recording[:, i] *= -1

        # trim the recording data to the length of the reamp data
        processed_recording = processed_recording[: len(reamp_audio), :]

        return processed_recording

    def capture(
        self,
        plot_latency: bool = False,
        latency_adjustment: LatencyAdjustment = LatencyAdjustment.BASE,
        inversion_adjustment: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._send_level_dbu is None:
            raise RuntimeError("reamp not calibrated. exitting...")

        # scale the reamp data using the reamp delta to output at the proper level
        reamp_audio = np.array(self.input_wav.data * db_to_scalar(0 - self._send_level_dbu), dtype=np.int32)
        # append 10 blocks of zeros to the end of the input data to account for latency
        raw_recording = np.zeros((len(reamp_audio) + 10 * self.blocksize, self.num_input_channels), dtype=np.int32)

        current_frame = 0
        recording_levels = np.zeros(self.num_input_channels, dtype=np.int32)
        recording_done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal recording_levels
            nonlocal current_frame
            chunksize = min(len(reamp_audio) - current_frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_output_channels))
            output[:chunksize, self.channels["reamp"] - 1] = reamp_audio[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            # read the recording data from the interface input channels
            input = unpack(indata, self.num_input_channels)
            raw_recording[current_frame : current_frame + frames] = input

            recording_levels[:] = np.max(np.abs(input), axis=0)
            current_frame += frames
            if current_frame >= len(reamp_audio):
                raise sd.CallbackStop()

        stream = sd.RawStream(
            samplerate=self.input_wav.rate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_input_channels, self.num_output_channels),
            dtype="int24",
            callback=callback,
            finished_callback=recording_done.set,
        )

        peak_levels = np.zeros(self.num_input_channels, dtype=np.int32)
        with stream:
            while not recording_done.wait(timeout=1.0):
                for i in range(self.num_input_channels):
                    if recording_levels[i] > peak_levels[i]:
                        peak_levels[i] = recording_levels[i]
                peak_dbfs = int_to_dbfs(peak_levels)
                output_str = " | ".join(f"{dbu:3.2f}" for dbu in peak_dbfs)
                current_seconds = current_frame // self.input_wav.rate
                current_seconds = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
                total_seconds = len(self.input_wav.data) // self.input_wav.rate
                total_seconds = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
                print(f"{current_seconds} / {total_seconds} - {output_str}          ")

        channel_delays, channel_inversions = self._calculate_latency(reamp_audio, raw_recording)

        processed_recording = self._process_recordings(
            reamp_audio,
            raw_recording,
            channel_delays,
            channel_inversions,
            inversion_adjustment=inversion_adjustment,
            latency_adjustment=latency_adjustment,
        )

        if plot_latency:
            for i in range(self.num_input_channels):
                samples = self.input_wav.rate * 5
                plt.figure(figsize=(16, 5))
                plt.plot(
                    reamp_audio[:samples] / np.max(reamp_audio[:samples]),
                    label="reamp",
                )
                plt.plot(
                    raw_recording[:samples, i] / np.max(raw_recording[:samples, i]),
                    linestyle="--",
                    label="raw recording",
                )
                plt.plot(
                    processed_recording[:samples, i] / np.max(processed_recording[:samples, i]),
                    linestyle="-.",
                    label="processed recording",
                )
                plt.title(
                    f"channel={i} | base delay={channel_delays[0]} | channel_delay={channel_delays[i]} | invert={channel_inversions[i]}"
                )
                plt.legend()
                plt.show(block=True)

        return raw_recording, processed_recording

    def testtone(
        self,
        output_level: float,
        unit: TestToneUnit = TestToneUnit.DBFS,
    ):
        if unit == TestToneUnit.DBU and self._send_level_dbu is None:
            raise RuntimeError("reamp not calibrated. exitting...")
        if unit == TestToneUnit.DBFS and output_level > 0.0:
            raise ValueError("output level must be negative for dbfs test tone")

        num_output_channels = self.channels["reamp"]

        def get_output_level_dbfs():
            if unit == TestToneUnit.DBFS:
                return output_level
            elif unit == TestToneUnit.DBU:
                return dbfs_to_dbu(output_level, self._send_level_dbu)

        sine_wave = SineWave(self.frequency, self.samplerate, get_output_level_dbfs())

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            output = np.zeros((frames, num_output_channels), dtype=np.int32)
            for i in range(frames):
                output[i, self.channels["reamp"] - 1] = next(sine_wave)
            outdata[:] = pack(output)

        stream = sd.RawOutputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=num_output_channels,
            dtype="int24",
            callback=callback,
        )

        with stream:
            print("enter 1 to increase output level, 2 to decrease output level, q to quit")
            control = "0"
            while control != "q":
                print("output level: ", output_level, "dbfs" if unit == TestToneUnit.DBFS else "dbu")
                if control == "1":
                    output_level += 1
                    sine_wave = SineWave(self.frequency, self.samplerate, get_output_level_dbfs())
                elif control == "2":
                    output_level -= 1
                    sine_wave = SineWave(self.frequency, self.samplerate, get_output_level_dbfs())
                elif control == "0" or control == "q":
                    pass
                else:
                    print("invalid input")
                control = input("> ")

    def reamp(self):
        if self._send_level_dbu is None:
            raise RuntimeError("reamp not calibrated. exitting...")

        # scale the reamp data using the reamp delta to output at the proper level
        reamp_audio = np.array(self.input_wav.data * db_to_scalar(0 - self._send_level_dbu), dtype=np.int32)

        current_frame = 0
        recording_done = threading.Event()

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal current_frame
            chunksize = min(len(reamp_audio) - current_frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_output_channels))
            output[:chunksize, self.channels["reamp"] - 1] = reamp_audio[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            current_frame += frames
            if current_frame >= len(reamp_audio):
                raise sd.CallbackStop()

        stream = sd.RawOutputStream(
            samplerate=self.input_wav.rate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_input_channels, self.num_output_channels),
            dtype="int24",
            callback=callback,
            finished_callback=recording_done.set,
        )

        with stream:
            while not recording_done.wait(timeout=1.0):
                current_seconds = current_frame // self.input_wav.rate
                current_seconds = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
                total_seconds = len(self.input_wav.data) // self.input_wav.rate
                total_seconds = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
                print(f"{current_seconds} / {total_seconds}")

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

        try:
            with stream:
                print("press ctrl+c to stop")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
