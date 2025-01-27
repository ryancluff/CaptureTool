import sys
import threading
import wavio

import numpy as np
import sounddevice as sd

from capture_tool.interface import Interface
from capture_tool.audio import pack, unpack, calculate_channel_dbfs


class Capture:
    def __init__(self, config: dict):
        self.blocksize = config["blocksize"]
        self.reamp_wav = wavio.read(config["reamp_file"])

    def get_total_time(self):
        return f"{(len(self.reamp_wav.data) // self.reamp_wav.rate) // 60:02d}:{(len(self.reamp_wav.data) // self.reamp_wav.rate) % 60:02d}"

    def get_current_time(self, current_frame):
        return f"{(current_frame // self.reamp_wav.rate) // 60:02d}:{(current_frame // self.reamp_wav.rate) % 60:02d}"

    def run(self, interface: Interface):
        if interface.reamp_dbu is None:
            raise RuntimeError("Interface not calibrated")

        recording = np.zeros(
            (len(self.reamp_wav.data) + 2 * self.blocksize, len(interface.channels["input"])), dtype=np.int32
        )

        current_frame = 0
        input_max = np.zeros(len(interface.channels["input"]), dtype=np.int32)
        recording_done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal current_frame
            chunksize = min(len(self.reamp_wav.data) - current_frame, frames)

            output = np.zeros((frames, interface.channels["output"]))
            output[:chunksize, interface.channels["output"] - 1] = self.reamp_wav.data[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = pack(output)

            input = unpack(indata, len(interface.channels["input"]))

            nonlocal input_max
            input_max[:] = np.max(np.abs(input), axis=0)

            recording[current_frame : current_frame + frames] = input

            current_frame += frames
            if current_frame >= len(self.reamp_wav.data):
                raise sd.CallbackStop()

        try:
            stream = sd.RawStream(
                samplerate=self.reamp_wav.rate,
                blocksize=self.blocksize,
                device=interface.device,
                channels=(len(interface.channels["input"]), interface.channels["output"]),
                dtype="int24",
                callback=callback,
                finished_callback=recording_done.set,
            )

            with stream:
                while not recording_done.wait(timeout=1.0):
                    input_dbfs = calculate_channel_dbfs(input_max)
                    output_str = " | ".join(f"{dbu:3.2f}" for dbu in input_dbfs)
                    print(f"{self.get_current_time()} / {self.get_total_time()} - {output_str}")

            for i in range(len(interface.channels["input"])):
                name = interface.channels["input"][i]
                wavio.write(f"capture-{name}.wav", recording[:, i - 1], self.reamp_wav.rate, sampwidth=3)

        except KeyboardInterrupt:
            pass
