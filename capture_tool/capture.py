from enum import Enum
from pathlib import Path
import sys
import threading
import wavio

import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd

from capture_tool.interface import Interface
from capture_tool.audio import pack, unpack, int_to_dbfs

LATENCY_OFFSET = 0


class LatencyAdjustment(Enum):
    NONE = 0
    BASE = 1
    INDIVIDUAL = 2


class Capture:
    def __init__(
        self,
        config: dict,
        interface: Interface,
    ):
        self.interface = interface
        self.input_wav = wavio.read(config["reamp_file"])

    def _get_total_time(self, reamp_wav: wavio.Wav) -> str:
        return (
            f"{(len(reamp_wav.data) // reamp_wav.rate) // 60:02d}:{(len(reamp_wav.data) // reamp_wav.rate) % 60:02d}"
        )

    def _get_current_time(self, current_frame: int, reamp_wav: wavio.Wav) -> str:
        return f"{(current_frame // reamp_wav.rate) // 60:02d}:{(current_frame // reamp_wav.rate) % 60:02d}"

    def _calculate_latency(
        self,
        reamp_data: np.ndarray,
        raw_recording: np.ndarray,
        cc_len: int = 5,
    ) -> tuple[np.ndarray, np.ndarray]:
        channel_delays = np.zeros(self.interface.num_input_channels, dtype=np.int32)
        channel_inversions = np.zeros(self.interface.num_input_channels, dtype=np.bool)

        # trim input and output data for cross correlation
        reamp_short = reamp_data[: self.input_wav.rate * cc_len, 0]
        recording_short = raw_recording[: self.input_wav.rate * cc_len, :]

        # normalize data to -1 to 1 to prevent overflow in cross correlation
        reamp_short = reamp_short / np.max(np.abs(reamp_short))
        for i in range(self.interface.num_input_channels):
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
            for i in range(self.interface.num_input_channels):
                processed_recording[: -channel_delays[i], i] = raw_recording[channel_delays[i] :, i]
        elif latency_adjustment == LatencyAdjustment.INDIVIDUAL:
            for i in range(self.interface.num_input_channels):
                processed_recording[: -channel_delays[0], i] = raw_recording[channel_delays[0] :, i]
        else:
            processed_recording[:, :] = raw_recording[:, :]

        # invert the recording data if necessary
        if inversion_adjustment:
            for i in range(self.interface.num_input_channels):
                if channel_inversions[i]:
                    print(f"detected signal inversion on channel {i}, correcting")
                    processed_recording[:, i] *= -1

        # trim the recording data to the length of the reamp data
        processed_recording = processed_recording[: len(reamp_audio), :]

        return processed_recording

    def run(
        self,
        plot_latency: bool = False,
        latency_adjustment: LatencyAdjustment = LatencyAdjustment.BASE,
        inversion_adjustment: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.interface.reamp_delta is None:
            raise RuntimeError("reamp not calibrated. exitting...")

        # scale the reamp data using the reamp delta to output at the proper level
        reamp_audio = np.array(self.input_wav.data * 10 ** ((0 - self.interface.reamp_delta) / 20), dtype=np.int32)
        # append 10 blocks of zeros to the end of the input data to account for latency
        raw_recording = np.zeros(
            (len(reamp_audio) + 10 * self.interface.blocksize, self.interface.num_input_channels), dtype=np.int32
        )

        current_frame = 0
        recording_levels = np.zeros(self.interface.num_input_channels, dtype=np.int32)
        recording_done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal recording_levels
            nonlocal current_frame
            chunksize = min(len(reamp_audio) - current_frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.interface.num_output_channels))
            output[:chunksize, self.interface.channels["reamp"] - 1] = reamp_audio[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            # read the recording data from the interface input channels
            input = unpack(indata, self.interface.num_input_channels)
            raw_recording[current_frame : current_frame + frames] = input

            recording_levels[:] = np.max(np.abs(input), axis=0)
            current_frame += frames
            if current_frame >= len(reamp_audio):
                raise sd.CallbackStop()

        stream = sd.RawStream(
            samplerate=self.input_wav.rate,
            blocksize=self.interface.blocksize,
            device=self.interface.device,
            channels=(self.interface.num_input_channels, self.interface.num_output_channels),
            dtype="int24",
            callback=callback,
            finished_callback=recording_done.set,
        )

        peak_levels = np.zeros(self.interface.num_input_channels, dtype=np.int32)
        with stream:
            while not recording_done.wait(timeout=1.0):
                for i in range(self.interface.num_input_channels):
                    if recording_levels[i] > peak_levels[i]:
                        peak_levels[i] = recording_levels[i]
                peak_dbfs = int_to_dbfs(peak_levels)
                output_str = " | ".join(f"{dbu:3.2f}" for dbu in peak_dbfs)
                print(
                    f"{self._get_current_time(current_frame, self.input_wav)} / {self._get_total_time(self.input_wav)} - {output_str}          "
                )

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
            for i in range(self.interface.num_input_channels):
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
