import sys
import threading

import numpy as np
from numpy import typing as npt

import sounddevice as sd
import wavio

from capture_tool.audio import int24_to_dbfs
from capture_tool.interface import AudioInterface
from capture_tool.wave import Wave, SineWave, AudioWave


class Stream:
    interface: AudioInterface
    send_audio: Wave

    stream: sd._StreamBase
    done: threading.Event

    def __init__(self, interface: AudioInterface, wave: Wave):
        if type(self) is Stream:
            raise Exception("Stream is an abstract class and cannot be instantiated directly")

        self.interface = interface
        self.send_audio = wave

        self.done = threading.Event()

    def __enter__(self) -> sd._StreamBase:
        self.stream.start()
        return self.stream

    def __exit__(self, *args) -> None:
        self.stream.stop()
        self.stream.close()

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
        super().__init__(interface, send_audio)

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if not self.send_audio.loop:
                chunksize = min(len(self.send_audio) - self.send_audio.frame, frames)
            else:
                chunksize = frames

            output = np.zeros((frames, self.interface.num_sends), dtype=np.int32)
            output[:chunksize, self.interface.num_sends - 1] = self.send_audio.next(chunksize)
            outdata[:] = self.pack(output)

        self.stream = sd.RawOutputStream(
            samplerate=self.send_audio.samplerate,
            blocksize=self.interface.blocksize,
            device=self.interface.device,
            channels=self.interface.num_sends,
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
        send_audio: Wave,
    ):
        super().__init__(interface, send_audio)

        self.return_audio = np.zeros(
            (len(self.send_audio) + 10 * self.interface.blocksize, self.interface.num_returns), dtype=np.int32
        )
        self.return_levels = np.zeros(self.interface.num_returns, dtype=np.int32)

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            if not self.send_audio.loop:
                chunksize = min(len(self.send_audio) - self.send_audio.frame, frames)
            else:
                chunksize = frames

            output = np.zeros((frames, self.interface.num_sends), dtype=np.int32)
            output[chunksize, self.interface.num_sends - 1] = self.send_audio.next(chunksize)
            outdata[:] = self.pack(output)

            input = self.unpack(indata, self.interface.num_returns)
            self.return_audio[self.send_audio.frame : self.send_audio.frame + frames] = input

            levels = np.max(np.abs(input), axis=0)
            for i in range(self.interface.num_returns):
                if levels[i] > self.return_levels[i]:
                    self.return_levels[i] = levels[i]

            self.send_audio.frame += frames
            if self.send_audio.frame >= len(self.send_audio):
                raise sd.CallbackStop()

        self.stream = sd.RawStream(
            samplerate=self.send_audio.samplerate,
            blocksize=self.interface.blocksize,
            device=self.interface.device,
            channels=(self.interface.num_returns, self.interface.num_sends),
            dtype="int24",
            callback=callback,
            finished_callback=self.done.set,
        )

    def get_return_levels(self) -> list[float]:
        return int24_to_dbfs(self.return_levels).tolist()


class SineWaveStream(SendStream):
    def __init__(
        self,
        interface: AudioInterface,
        level_dbfs: float,
    ):
        sine_wave = SineWave(dbfs=level_dbfs)
        super().__init__(interface, sine_wave)

    def get_send_level(self) -> float:
        return self.send_audio.get_level()

    def increase_send_level(self):
        self.send_audio.set_level(self.send_audio.dbfs + 1)

    def decrease_send_level(self):
        self.send_audio.set_level(self.send_audio.dbfs - 1)


class SendCalibrationStream(SendStream):
    def __init__(
        self,
        interface: AudioInterface,
        level_dbfs: float,
    ):
        sine_wave = SineWave(dbfs=level_dbfs)
        super().__init__(interface, sine_wave)


class ReturnCalibrationStream(SendReturnStream):
    def __init__(
        self,
        interface: AudioInterface,
        level_dbfs: float,
    ):
        sine_wave = SineWave(dbfs=level_dbfs)
        super().__init__(interface, sine_wave)


class CaptureStream(SendReturnStream):
    def __init__(
        self,
        interface: AudioInterface,
        input_wav: wavio.Wav,
    ):
        send_audio = AudioWave(input_wav.data)
        super().__init__(interface, send_audio)
