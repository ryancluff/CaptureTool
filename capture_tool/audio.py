import math

import numpy as np

MAX_VAL_INT24 = 2 ** (24 - 1) - 1


def db_to_scalar(db: float) -> float:
    return 10 ** (db / 20)


# Convert RMS voltage to dBu
def v_rms_to_dbu(v_rms: float) -> float:
    return 20 * math.log10(v_rms / 0.7746)


# Convert dBu to RMS voltage
def dbu_to_v_rms(dbu: float) -> float:
    return 0.7746 * 10 ** (dbu / 20)


# Convert 24 bit audio data to dBFS
def int_to_dbfs(max_val: np.array) -> np.array:
    return 20 * np.log10(max_val / (MAX_VAL_INT24))
