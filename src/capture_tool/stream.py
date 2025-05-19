from enum import Enum
import sys
import threading

import numpy as np
from numpy import typing as npt

import sounddevice as sd
import wavio

from capture_tool.interface import AudioInterface
from capture_tool.wave import Wave, SineWave


class Stream:
    interface: AudioInterface
    send_audio: Wave

    stream: sd._StreamBase
    done: threading.Event

    def __init__(self, interface: AudioInterface):
        if type(self) is Stream:
            raise Exception("Stream is an abstract class and cannot be instantiated directly")

        self.interface = interface
        self.done = threading.Event()

    @staticmethod
    def pack(data: npt.NDArray[np.int32]) -> bytes:
        return b"".join(
            int(sample).to_bytes(
                3,
                byteorder="little",
                signed=True,
            )
            for sample in data.flatten()
        )

    @staticmethod
    def unpack(data: bytes, channels: int) -> npt.NDArray[np.int32]:
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
        interface: AudioInterface,
        send_audio: Wave,
    ):
        super().__init__(interface)

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if not send_audio.loop:
                chunksize = min(len(send_audio) - send_audio.frame, frames)
            else:
                chunksize = frames

            output = np.zeros((frames, interface.num_sends), dtype=np.int32)
            output[chunksize, interface.num_sends - 1] = send_audio.of_length(samples=chunksize)
            outdata[:] = self.pack(output)

        self.stream = sd.RawOutputStream(
            samplerate=send_audio.samplerate,
            blocksize=interface.blocksize,
            device=interface.device,
            channels=interface.num_sends,
            dtype="int24",
            callback=callback,
            finished_callback=self.done.set,
        )


class SendReturnStream(Stream):
    return_audio: npt.NDArray[np.int32]
    return_levels: npt.NDArray[np.int32]

    def __init__(
        self,
        interface: AudioInterface,
        output_level: float,
        unit: TestToneUnit = TestToneUnit.DBFS,
    ):
        self.output_level = output_level
        self.unit = unit
        self.sine_wave = SineWave(dbfs=self._get_level_dbfs())

        super().__init__(interface, self.sine_wave)

    def _get_level_dbfs(self):
        if self.unit == self.TestToneUnit.DBFS:
            return self.output_level
        elif self.unit == self.TestToneUnit.DBU:
            return self.interface.send_dbfs_to_dbu(self.output_level)

    def increase_output_level(self):
        self.output_level += 1
        self.sine_wave = SineWave(self.frequency, self.samplerate, self._get_level_dbfs())

    def decrease_output_level(self):
        self.output_level -= 1
        self.sine_wave = SineWave(self.frequency, self.samplerate, self._get_level_dbfs())


class SendReturnStream(Stream):
    pass
