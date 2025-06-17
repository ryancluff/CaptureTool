import numpy as np
from numpy import typing as npt


class Wave:
    MAX_VAL_INT24: int = 2 ** (24 - 1) - 1

    frame: int
    unscaled_audio: npt.NDArray[np.int32]
    audio: npt.NDArray[np.int32]

    samplerate: int
    level_dbfs: float
    loop: bool

    @staticmethod
    def db_to_scalar(db: float) -> float:
        return 10 ** (db / 20.0)

    def __init__(
        self,
        audio_data: npt.NDArray[np.int32],
        samplerate: int,
        level_dbfs: float,
        loop: bool = False,
    ):
        if type(self) is Wave:
            raise Exception("Wave is an abstract class and cannot be instantiated directly")

        self.frame = 0

        self.samplerate = samplerate
        self.level_dbfs = level_dbfs
        self.loop = loop
        self.unscaled_audio = audio_data

        self.audio = (self.unscaled_audio * self.db_to_scalar(level_dbfs)).astype(np.int32)

    def __iter__(self):
        return self

    def __next__(self):
        if self.frame >= len(self.audio):
            if self.loop:
                self.frame = 0
            else:
                raise StopIteration
        result = self.audio[self.frame]
        self.frame += 1
        return result

    def __len__(self):
        return len(self.audio)

    def reset(self):
        self.frame = 0

    def next(self, samples: int) -> npt.NDArray[np.int32]:
        iterable = (next(self) for _ in range(samples))
        return np.fromiter(iterable, dtype=np.int32)

    def get_level(self) -> float:
        return self.level_dbfs

    def set_level(self, dbfs: float):
        self.level_dbfs = dbfs
        self.audio = (self.unscaled_audio * self.db_to_scalar(dbfs)).astype(np.int32)

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_time(self) -> str:
        seconds = self.frame / self.samplerate
        return self._format_time(seconds)

    def get_duration(self) -> str:
        seconds = len(self.audio) / self.samplerate
        return self._format_time(seconds)


class SineWave(Wave):
    def __init__(
        self,
        frequency: float,
        samplerate: int,
        level_dbfs: float,
    ):
        duration = 1 / frequency
        t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
        phase = 2 * np.pi * frequency * t
        w = (self.MAX_VAL_INT24 * np.sin(phase)).astype(np.int32)

        super().__init__(w, samplerate, level_dbfs, loop=True)


class SweepWave(Wave):
    def __init__(
        self,
        freq_start: float,
        freq_end: float,
        duration: float,
        samplerate: int,
        level_dbfs: float,
    ):
        t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
        beta = (freq_end - freq_start) / duration
        phase = 2 * np.pi * (freq_start * t + 0.5 * beta * t * t)
        w = (self.MAX_VAL_INT24 * np.sin(phase)).astype(np.int32)

        super().__init__(w, samplerate, level_dbfs)


class AudioWave(Wave):
    def __init__(
        self,
        audio_data: npt.NDArray[np.int32],
        samplerate: int,
        level_dbfs: float,
    ):
        super().__init__(audio_data, samplerate, level_dbfs)
