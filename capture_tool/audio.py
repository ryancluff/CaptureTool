import math

import numpy as np


class SineWave:
    def __init__(
        self,
        frequency: float = 1000.0,
        samplerate: int = 48000,
        dbfs: float = -12.0,
    ):
        amplitude = 10 ** (dbfs / 20.0)
        max_val = 2 ** (24 - 1) - 1
        self.samplerate = samplerate
        self.period = int(samplerate / frequency)
        self.lookup_table = np.array(
            [
                int(
                    max_val
                    * amplitude
                    * math.sin(2.0 * math.pi * frequency * (float(i % self.period) / float(samplerate)))
                )
                for i in range(self.period)
            ]
        )
        self.position = 0

    def __next__(self):
        value = self.lookup_table[self.position % self.period]
        self.position += 1
        return value

    def __iter__(self):
        return self

    def of_length(self, seconds: float = 2, samples: int = None) -> np.array:
        if samples is not None:
            return np.array([next(self) for _ in range(samples)])
        return np.array([next(self) for _ in range(int(seconds * self.samplerate))])


# Convert floating-point audio data to 24-bit data
def pack(data: np.array) -> bytes:
    return b"".join(int(sample).to_bytes(3, byteorder="little", signed=True) for sample in data.flatten())


# Convert 24-bit data to floating-point audio data
def unpack(data: bytes, channels: int) -> np.array:
    return np.array(
        [int.from_bytes(data[i : i + 3], "little", signed=True) for i in range(0, len(data), 3)], dtype=np.int32
    ).reshape((-1, channels))


# Convert RMS voltage to dBu
def v_rms_to_dbu(v_rms: float) -> float:
    return 20 * math.log10(v_rms / 0.7746)


# Convert dBu to RMS voltage
def dbu_to_v_rms(dbu: float) -> float:
    return 0.7746 * 10 ** (dbu / 20)


# Convert dBu to dBFS
def dbu_to_dbfs(dbu: float, delta: float) -> float:
    return dbu - delta


# Convert dBFS to dBu
def dbfs_to_dbu(dbfs: float, delta: float) -> float:
    return dbfs + delta


# Convert 24 bit audio data to dBFS
def int_to_dbfs(input_max: np.array) -> np.array:
    return 20 * np.log10(input_max / (2 ** (24 - 1) - 1))
