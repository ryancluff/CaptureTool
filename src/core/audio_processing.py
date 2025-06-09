from enum import Enum

import numpy as np
import numpy.typing as npt

LATENCY_OFFSET = 0


class LatencyAdjustment(Enum):
    NONE = 0
    BASE = 1
    INDIVIDUAL = 2


def calculate_latency(
    send_audio: npt.NDArray[np.int32],
    return_audio: npt.NDArray[np.int32],
    samplerate: int,
    cross_correlation_seconds: int = 5,
) -> tuple[list[int], list[bool]]:
    num_returns = np.shape(return_audio)[1]
    channel_delays = [0 for _ in range(num_returns)]
    channel_inversions = [False for _ in range(num_returns)]

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
        channel_delays[i] = len(recording_short) - int(max_cc) - 1 - LATENCY_OFFSET
    return channel_delays, channel_inversions


def process_recordings(
    send_audio: npt.NDArray[np.int32],
    return_audio: npt.NDArray[np.int32],
    channel_delays: list[int],
    channel_inversions: list[bool],
    latency_adjustment: LatencyAdjustment = LatencyAdjustment.BASE,
    inversion_adjustment: bool = True,
) -> npt.NDArray:
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
