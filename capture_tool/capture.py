from pathlib import Path
import sys
import threading
import wavio

import numpy as np
import sounddevice as sd

from capture_tool.interface import Interface
from capture_tool.audio import pack, unpack, int_to_dbfs


class Capture:
    def __init__(self, config: dict):
        self.blocksize = config["blocksize"]
        self.reamp_file = config["reamp_file"]

    def get_total_time(self, reamp_wav):
        return (
            f"{(len(reamp_wav.data) // reamp_wav.rate) // 60:02d}:{(len(reamp_wav.data) // reamp_wav.rate) % 60:02d}"
        )

    def get_current_time(self, current_frame, reamp_wav):
        return f"{(current_frame // reamp_wav.rate) // 60:02d}:{(current_frame // reamp_wav.rate) % 60:02d}"

    def run(self, interface: Interface, capture_dir: Path):
        if interface.reamp_delta is None:
            raise RuntimeError("Interface not calibrated")

        reamp_wav = wavio.read(self.reamp_file)
        reamp_wav_adjusted = reamp_wav.data * 10 ** ((0 - interface.reamp_delta) / 20)

        num_output_channels = interface.channels["reamp"]
        num_input_channels = len(interface.channels["input"])

        recording = np.zeros((len(reamp_wav_adjusted) + 2 * self.blocksize, num_input_channels), dtype=np.int32)

        current_frame = 0
        input_level = np.zeros(num_input_channels, dtype=np.int32)
        recording_done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal current_frame
            chunksize = min(len(reamp_wav_adjusted) - current_frame, frames)

            output = np.zeros((frames, num_output_channels))
            output[:chunksize, interface.channels["reamp"] - 1] = reamp_wav_adjusted[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            input = unpack(indata, num_input_channels)

            nonlocal input_level
            input_level[:] = np.max(np.abs(input), axis=0)

            recording[current_frame : current_frame + frames] = input

            current_frame += frames
            if current_frame >= len(reamp_wav_adjusted):
                raise sd.CallbackStop()

        try:
            stream = sd.RawStream(
                samplerate=reamp_wav.rate,
                blocksize=self.blocksize,
                device=interface.device,
                channels=(num_input_channels, num_output_channels),
                dtype="int24",
                callback=callback,
                finished_callback=recording_done.set,
            )

            input_max = np.zeros(num_input_channels, dtype=np.int32)
            with stream:
                while not recording_done.wait(timeout=1.0):
                    for i in range(num_input_channels):
                        if input_level[i] > input_max[i]:
                            input_max[i] = input_level[i]
                    input_max_dbfs = int_to_dbfs(input_max)
                    output_str = " | ".join(f"{dbu:3.2f}" for dbu in input_max_dbfs)
                    print(
                        f"{self.get_current_time(current_frame, reamp_wav)} / {self.get_total_time(reamp_wav)} - {output_str}          "
                    )

            for i in range(interface.channels["input"]):
                channel = interface.channels["input"][i]
                wavio.write(str(Path(capture_dir, f"recording-{channel}.wav")), recording[:, i], reamp_wav.rate, sampwidth=3)

        except KeyboardInterrupt:
            pass
