import sys
import math
import time

import numpy as np
from scipy.fft import fft

import pyaudio

import matplotlib.pyplot as plt

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

    chunk = 1024

    db_fs = -6
    frequency = 1000

    in_channel = 1  # 1-based index
    in_channels = 1
    out_channel = 3  # 1-based index
    out_channels = 4

    sine_wave = SineWave(frequency, samplerate, db_fs)

    # Define callback for playback
    def play_callback(in_data, frame_count, time_info, status):
        if status:
            print(status, file=sys.stderr)

        npdata = np.zeros((frame_count, out_channels))

        for i in range(frame_count):
            npdata[i, out_channel - 1] = next(sine_wave)

        data_bytes = pack(npdata.flatten())
        return (data_bytes, pyaudio.paContinue)

    # Instantiate PyAudio and initialize PortAudio system resources
    p = pyaudio.PyAudio()

    # Print all devices
    for i in range(p.get_device_count()):
        print(p.get_device_info_by_index(i))

    # Print all host APIs
    for i in range(p.get_host_api_count()):
        print(p.get_host_api_info_by_index(i))

    out_stream = p.open(
        format=pyaudio.paInt24,
        channels=out_channels,
        rate=samplerate,
        output_device_index=device_index,
        output=True,
        stream_callback=play_callback,
    )

    time.sleep(1)

    in_stream = p.open(
        format=pyaudio.paInt24,
        channels=in_channels,
        rate=samplerate,
        output_device_index=device_index,
        input=True,
    )

    window = np.zeros([], dtype=np.float32)
    for _ in range(0, samplerate // chunk * 5):
        npdata = unpack(in_stream.read(chunk))
        npdata = npdata.reshape(chunk, in_channels)
        window = np.append(window, npdata[::, in_channel - 1])

    # Clean up
    in_stream.stop_stream()
    out_stream.stop_stream()
    in_stream.close()
    out_stream.close()
    p.terminate()


    window_fft = fft(window)

    plt.plot(window_fft)
    plt.show(block=True)

    print(window_fft)


if __name__ == "__main__":
    main()
