import math

import numpy as np


class SineWave:
    def __init__(self, frequency: float = 1000.0, samplerate: int = 44100, dbfs: float = -12.0):
        amplitude = 10 ** (dbfs / 20.0)
        self.period = int(samplerate / frequency)
        self.lookup_table = [
            amplitude * math.sin(2.0 * math.pi * frequency * (float(i % self.period) / float(samplerate)))
            for i in range(self.period)
        ]
        self.idx = 0

    def __next__(self):
        value = self.lookup_table[self.idx % self.period]
        self.idx += 1
        return value

    def __iter__(self):
        return self


def pack(data: np.array) -> bytes:
    # Convert floating-point audio data to 24-bit data
    return b"".join((int(8388607.0 * sample)).to_bytes(3, byteorder="little", signed=True) for sample in data)


def unpack(data: bytes) -> np.array:
    # Convert 24-bit data to floating-point audio data
    return np.array(
        [int.from_bytes(data[i : i + 3], "little", signed=True) / 8388607.0 for i in range(0, len(data), 3)]
    )