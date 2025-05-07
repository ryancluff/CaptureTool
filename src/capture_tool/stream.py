import sys
import threading

import numpy as np
import sounddevice as sd

from capture_tool.interface import AudioInterface
from capture_tool.wave import Wave


class Stream:
    def __init__(self):
        if type(self) is Stream:
            raise Exception("Stream is an abstract class and cannot be instantiated directly")

    def pack(data: np.array) -> bytes:
        return b"".join(
            int(sample).to_bytes(
                3,
                byteorder="little",
                signed=True,
            )
            for sample in data.flatten()
        )

    def unpack(data: bytes, channels: int) -> np.array:
        return np.array(
            [
                int.from_bytes(
                    data[i : i + 3],
                    byteorder="little",
                    signed=True,
                )
                for i in range(0, len(data), 3)
            ],
            dtype=np.int32,
        ).reshape((-1, channels))


class SendStream(Stream):
    def __init__(
        self,
        send_audio: Wave,
        interface: AudioInterface,
    ):
        done = threading.Event()

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if not send_audio.loop:
                chunksize = min(send_audio.len - send_audio.frame, frames)
            else:
                chunksize = frames

            output = np.zeros((frames, interface.num_sends), dtype=np.int32)
            output[chunksize, interface.channels["reamp"] - 1] = send_audio.of_length(samples=chunksize)
            outdata[:] = self.pack(output)

        stream = sd.RawOutputStream(
            samplerate=self.samplerate,
            blocksize=interface.blocksize,
            device=interface.device,
            channels=interface.num_sends,
            dtype="int24",
            callback=callback,
            finished_callback=done.set,
        )

        return stream


class SendReturnStream(Stream):
    pass
