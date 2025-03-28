import math

import numpy as np


class Wave:
    MAX_VAL_INT24 = 2 ** (24 - 1) - 1

    @classmethod
    def db_to_scalar(cls, db: float) -> float:
        return 10 ** (db / 20.0)

    # Convert 24 bit audio data to dBFS
    @classmethod
    def int_to_dbfs(cls, max_val: np.array) -> np.array:
        return 20 * np.log10(max_val / (cls.MAX_VAL_INT24))

    def __init__(
        self,
        samplerate: int = 48000,
        dbfs: float = 0.0,
        loop: bool = False,
    ):
        self.position = 0
        self.samplerate = samplerate
        self.dbfs = dbfs
        self.loop = loop

    def __iter__(self):
        return self

    def __next__(self):
        if self.position >= len(self.lookup_table):
            if self.loop:
                self.position = 0
            else:
                raise StopIteration
        value = self.lookup_table[self.position]
        self.position += 1
        return value

    def of_length(self, seconds: float = 2, samples: int = None) -> np.array:
        if samples is not None:
            return np.array([next(self) for _ in range(samples)])
        return np.array([next(self) for _ in range(int(seconds * self.samplerate))])


class SineWave(Wave):
    def __init__(
        self,
        frequency: float = 1000.0,
        samplerate: int = 48000,
        dbfs: float = -12.0,
        loop: bool = True,
    ):
        super().__init__(
            samplerate=samplerate,
            dbfs=dbfs,
            loop=loop,
        )
        self.period = int(samplerate / frequency)
        self.lookup_table = np.array(
            [
                int(
                    self.MAX_VAL_INT24
                    * self.db_to_scalar(dbfs)
                    * math.sin(2.0 * math.pi * frequency * (float(i % self.period) / float(samplerate)))
                )
                for i in range(self.period)
            ]
        )


class AudioWave(Wave):
    def __init__(
        self,
        audio: np.array,
        samplerate: int = 48000,
        dbfs: float = 0.0,
        loop: bool = False,
    ):
        super().__init__(
            samplerate=samplerate,
            dbfs=dbfs,
            loop=loop,
        )
        self.period = len(audio)
        self.lookup_table = self.db_to_scalar(dbfs) * audio
