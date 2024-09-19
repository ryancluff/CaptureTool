import sys
import math
import queue
import shutil
import time

import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


class SineWave:
    def __init__(
        self, frequency: float = 1000.0, samplerate: int = 44100, db_fs: float = -12.0
    ):
        amplitude = 10 ** (db_fs / 20.0)
        self.period = int(samplerate / frequency)
        self.lookup_table = [
            amplitude
            * math.sin(
                2.0 * math.pi * frequency * (float(i % self.period) / float(samplerate))
            )
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
    return b"".join(
        (int(8388607.0 * sample)).to_bytes(3, byteorder="little", signed=True)
        for sample in data
    )


def unpack(data: bytes) -> np.array:
    # Convert 24-bit data to floating-point audio data
    return np.array(
        [
            int.from_bytes(data[i : i + 3], "little", signed=True) / 8388607.0
            for i in range(0, len(data), 3)
        ]
    )


def main():
    device_index = 6
    samplerate = 96000

    chunk = 960

    db_fs = -6
    frequency = 1000

    n = 5

    in_channel = 1  # 1-based index
    in_channels = 4
    out_channel = 1  # 1-based index
    out_channels = 4

    magnitude = np.zeros(n)
    sine_wave = SineWave(frequency, samplerate, db_fs)

    # plot
    window = 200
    downsample = 10
    q = queue.Queue()
    length = int(window * samplerate / (1000 * downsample))
    plotdata = np.zeros((length, 2))
    fig, ax = plt.subplots()

    lines = ax.plot(plotdata)
    ax.legend(["output", "input"], loc="lower left", ncol=2)
    ax.axis((0, len(plotdata), -1, 1))
    ax.set_yticks([0, 0.5])
    ax.yaxis.grid(True)
    ax.tick_params(
        bottom=False,
        top=False,
        labelbottom=False,
        right=False,
        left=False,
        labelleft=False,
    )
    fig.tight_layout(pad=0)

    try:

        def update_plot(frame):
            """This is called by matplotlib for each plot update.

            Typically, audio callbacks happen more frequently than plot updates,
            therefore the queue tends to contain multiple blocks of audio data.

            """
            nonlocal plotdata
            while True:
                try:
                    data = q.get_nowait()
                except queue.Empty:
                    break
                shift = data.shape[0]
                plotdata = np.roll(plotdata, -shift, axis=0)
                plotdata[-shift:, :] = data

            for column, line in enumerate(lines):
                line.set_ydata(plotdata[:, column])
            return lines

        # Define callback for playback
        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            plot = np.zeros((frames, 2))

            output = np.zeros((frames, out_channels))
            for i in range(frames):
                output[i, out_channel - 1] = next(sine_wave)
            outdata[:] = pack(output.flatten())

            input = unpack(indata).reshape((frames, in_channels))
            nonlocal magnitude
            magnitude = np.abs(np.fft.fft(input[:, in_channel - 1], n=n))

            plot[:, 0] = output[:, out_channel - 1]
            plot[:, 1] = input[:, in_channel - 1]
            q.put(plot)

        stream = sd.RawStream(
            samplerate=samplerate,
            blocksize=chunk,
            device=device_index,
            channels=(in_channels, out_channels),
            dtype="int24",
            callback=callback,
        )

        ani = FuncAnimation(fig, update_plot, interval=200, blit=True)
        with stream:
            plt.show()
            while True:
                print("Magnitude: ", magnitude)
                time.sleep(1.1)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
