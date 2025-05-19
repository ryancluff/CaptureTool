import math
from enum import Enum

import numpy as np

MAX_VAL_INT24 = 2 ** (24 - 1) - 1


def db_to_scalar(db: float) -> float:
    return 10 ** (db / 20.0)


# Convert RMS voltage to dBu
def vrms_to_dbu(vrms: float) -> float:
    return 20 * math.log10(vrms / 0.7746)


# Convert dBu to RMS voltage
def dbu_to_vrms(dbu: float) -> float:
    return 0.7746 * 10 ** (dbu / 20)


# Convert 24 bit audio data to dBFS
def int_to_dbfs(max_val: np.ndarray) -> np.ndarray:
    return 20 * np.log10(max_val / (MAX_VAL_INT24))


LATENCY_OFFSET = 0


class LatencyAdjustment(Enum):
    NONE = 0
    BASE = 1
    INDIVIDUAL = 2


def calculate_latency(
    send_audio: np.ndarray,
    return_audio: np.ndarray,
    samplerate: int,
    cross_correlation_seconds: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    num_returns = np.shape(return_audio)[1]
    channel_delays = np.zeros(num_returns, dtype=np.int32)
    channel_inversions = np.zeros(num_returns, dtype=np.bool)

    # trim return and output data for cross correlation
    reamp_short = send_audio[: samplerate * cross_correlation_seconds, 0]
    recording_short = return_audio[: samplerate * cross_correlation_seconds, :]

    # normalize data to -1 to 1 to prevent overflow in cross correlation
    reamp_short = reamp_short / np.max(np.abs(reamp_short))
    for i in range(num_returns):
        output_data_short_normalized = recording_short[:, i] / np.max(np.abs(recording_short[:, i]))

        # calculate cross correlation for each channel
        # if the maximum cross correlation is negative, invert the channel
        cross_corr = np.correlate(reamp_short, output_data_short_normalized, mode="full")
        max_cc = np.argmax(cross_corr)
        min_cc = np.argmin(cross_corr)
        if np.abs(cross_corr[max_cc]) < np.abs(cross_corr[min_cc]):
            max_cc = min_cc
            channel_inversions[i] = True

        # Calculate the delay for each channel
        channel_delays[i] = len(recording_short) - max_cc - 1 - LATENCY_OFFSET
    return channel_delays, channel_inversions


def process_recordings(
    send_audio: np.ndarray,
    return_audio: np.ndarray,
    channel_delays: np.ndarray,
    channel_inversions: np.ndarray,
    latency_adjustment: LatencyAdjustment = LatencyAdjustment.BASE,
    inversion_adjustment: bool = True,
) -> np.ndarray:
    num_returns = np.shape(return_audio)[1]
    result = np.zeros_like(return_audio)

    # apply the calculated delays to the recording data
    if latency_adjustment == LatencyAdjustment.BASE:
        for i in range(num_returns):
            result[: -channel_delays[i], i] = return_audio[channel_delays[i] :, i]
    elif latency_adjustment == LatencyAdjustment.INDIVIDUAL:
        for i in range(num_returns):
            result[: -channel_delays[0], i] = return_audio[channel_delays[0] :, i]
    else:
        result[:, :] = return_audio[:, :]

    # invert the recording data if necessary
    if inversion_adjustment:
        for i in range(num_returns):
            if channel_inversions[i]:
                print(f"detected signal inversion on channel {i}, correcting")
                result[:, i] *= -1

    # trim the recording data to the length of the reamp data
    result = result[: len(send_audio), :]

    return result
