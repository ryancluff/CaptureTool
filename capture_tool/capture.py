import sys
import threading
import wavio

import numpy as np
import sounddevice as sd

from capture_tool.util import pack, unpack, calculate_channel_dbfs
from capture_tool.interface import Interface

class Capture:
    def __init__(self, config: dict):
        self.blocksize = config["blocksize"]
        self.reamp_file = config["reamp_file"]


    def run(self, interface: Interface):
        if interface.output_level is None:
            raise RuntimeError("Interface not calibrated")

        reamp_wav = wavio.read(self.reamp_file)
        reamp_data = reamp_wav.data
        reamp_time = f"{(len(reamp_data) // reamp_wav.rate) // 60:02d}:{(len(reamp_data) // reamp_wav.rate) % 60:02d}"

        recording = np.zeros((len(reamp_wav.data) + 2 * self.blocksize, len(interface.input_channels)), dtype=np.int32)

        current_frame = 0
        input_max = np.zeros(len(interface.input_channels), dtype=np.int32)
        recording_done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal current_frame
            chunksize = min(len(reamp_data) - current_frame, frames)

            output = np.zeros((frames, interface.output_channel))
            output[:chunksize, interface.output_channel - 1] = reamp_data[current_frame : current_frame + chunksize].flatten()
            outdata[:] = pack(output)

            input = unpack(indata, len(interface.input_channels))

            nonlocal input_max
            input_max[:] = np.max(np.abs(input), axis=0)

            recording[current_frame : current_frame + frames] = input

            current_frame += frames
            if current_frame >= len(reamp_data):
                raise sd.CallbackStop()

        try:
            stream = sd.RawStream(
                samplerate=reamp_wav.rate,
                blocksize=self.blocksize,
                device=interface.device,
                channels=(len(interface.input_channels), interface.output_channel),
                dtype="int24",
                callback=callback,
                finished_callback=recording_done.set,
            )

            with stream:
                while not recording_done.wait(timeout=1.0):
                    current_time = (
                        f"{(current_frame // reamp_wav.rate) // 60:02d}:{(current_frame // reamp_wav.rate) % 60:02d}"
                    )
                    input_dbfs = calculate_channel_dbfs(input_max)
                    output_str = " | ".join(f"{dbu:.2f}" for dbu in input_dbfs)
                    print(f"{current_time} / {reamp_time} - {output_str}")

            for i in range(len(interface.input_channels)):
                name = interface.input_channels[i]
                wavio.write(f"capture-{name}.wav", recording[:, i - 1], reamp_wav.rate, sampwidth=3)

        except KeyboardInterrupt:
            pass

