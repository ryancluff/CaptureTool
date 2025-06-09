import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt


def plot_latency(
    channel: int,
    samplerate: int,
    send_audio: npt.NDArray[np.int32],
    return_audio: npt.NDArray[np.int32],
    processed_return_audio: npt.NDArray[np.int32],
    channel_delays: list[int],
    channel_inversions: list[bool],
) -> None:
    samples = samplerate * 5
    plt.figure(figsize=(16, 5))
    plt.plot(
        np.divide(send_audio[:samples], np.max(send_audio[:samples])),
        label="reamp",
    )
    plt.plot(
        np.divide(return_audio[:samples, channel], np.max(return_audio[:samples, channel])),
        linestyle="--",
        label="raw recording",
    )
    plt.plot(
        np.divide(processed_return_audio[:samples, channel], np.max(processed_return_audio[:samples, channel])),
        linestyle="-.",
        label="processed recording",
    )
    plt.title(
        f"channel={channel} | base delay={channel_delays[0]} | channel_delay={channel_delays[channel]} | invert={channel_inversions[channel]}"
    )
    plt.legend()
    plt.show(block=True)
