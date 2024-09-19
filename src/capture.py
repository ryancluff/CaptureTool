import queue
import sys
import math
import threading
import time
import wavio

import numpy as np
import sounddevice as sd

from util import pack, unpack


def run():
    device_index = 6
    in_channels = 4
    out_channel = 3  # 1-based index
    out_channels = 4

    chunk = 960

    sample_file = wavio.read("v3_0_0.wav")

    current_frame = 0
    recording = np.zeros((len(sample_file.data) + 10, in_channels))

    q = queue.Queue(maxsize=args.buffersize)
    event = threading.Event()

    # Define callback for playback
    def callback(indata, outdata, frames, time, status):
        assert frames == chunk
        if status.output_underflow:
            print("Output underflow: increase blocksize?", file=sys.stderr)
            raise sd.CallbackAbort
        assert not status

        try:
            data = q.get_nowait()
        except queue.Empty:
            print("Buffer is empty: increase buffersize?", file=sys.stderr)
            raise sd.CallbackAbort
        
        if len(data) < len(outdata):
            outdata[: len(data)] = data
            outdata[len(data):] = b"\x00" * (len(outdata) - len(data))
            raise sd.CallbackStop

        output = np.zeros((frames, out_channels))
        for i in range(frames):
            output[i, out_channel - 1] = next(playback_iter)
        outdata[:] = pack(output.flatten())

        input = unpack(indata).reshape((frames, in_channels))

    try:

        stream = sd.RawStream(
            samplerate=sample_file.rate,
            blocksize=chunk,
            device=device_index,
            channels=(in_channels, out_channels),
            dtype="int24",
            callback=callback,
        )

        with stream:
            reamp_v_rms = input("Enter reamp rms Voltage: ")
            reamp_dbu = 20 * math.log10(float(reamp_v_rms) / 0.7746)
            db_fs = 12 - reamp_dbu
            while True:
                print("Magnitude: ", v_rms)
                time.sleep(1)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
