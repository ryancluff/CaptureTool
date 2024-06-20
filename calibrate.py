import sys
import math

import pyaudio


class SineWave:
    def __init__(
        self, frequency: float = 1000.0, samplerate: int = 44100, dbfs: float = -12.0
    ):
        self.frequency = frequency
        self.samplerate = samplerate
        self.amplitude = 10 ** (dbfs / 20.0)
        self.period = int(samplerate / frequency)
        self.lookup_table = [
            self.amplitude
            * math.sin(
                2.0
                * math.pi
                * self.frequency
                * (float(i % self.period) / float(self.samplerate))
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

    def __call__(self, num_samples):
        return [self.__next__() for _ in range(num_samples)]


def pack(data: list) -> bytes:
    # Convert floating-point audio data to 24-bit data
    return b"".join(
        (int(8388607.0 * sample)).to_bytes(3, byteorder="little", signed=True)
        for sample in data
    )


def main():
    device_index = 6
    samplerate = 96000

    dbfs = -12
    frequency = 1000

    in_channel = 1  # 1-based index
    in_channels = 1
    out_channel = 3  # 1-based index
    out_channels = 4

    sine_wave = SineWave(frequency, samplerate, dbfs)

    # Define callback for playback
    def play_callback(in_data, frame_count, time_info, status):
        if status:
            print(status, file=sys.stderr)
        data = []
        length = frame_count * out_channels
        for i in range(length):
            if (i % out_channels) + 1 == out_channel:
                data.append(next(sine_wave))
            else:
                data.append(0)
        data_bytes = pack(data)
        return (data_bytes, pyaudio.paContinue)

    j = 0
    peak_dbfs = 0

    # # Define callback for recording
    # def record_callback(in_data, frame_count, time_info, status):
    #     nonlocal peak_dbfs
    #     nonlocal j
    #     if status:
    #         print(status, file=sys.stderr)
    #     length = frame_count * out_channels
    #     for i in range(length):
    #         if (i % out_channels) + 1 == in_channel:
    #             current_dbfs = 20.0 * math.log10(abs(int(in_data[i]) / 8388607.0))
    #             if peak_dbfs < current_dbfs:
    #                 peak_dbfs = current_dbfs

    #     j += 1
    #     if j >= 48000:
    #         print("Peak dBFS: " + peak_dbfs)
    #         j = 0

    #     return (None, pyaudio.paContinue)

    # Instantiate PyAudio and initialize PortAudio system resources
    p = pyaudio.PyAudio()

    # # Print all devices
    # for i in range(p.get_device_count()):
    #     print(p.get_device_info_by_index(i))

    # # Print all host APIs
    # for i in range(p.get_host_api_count()):
    #     print(p.get_host_api_info_by_index(i))

    # in_stream = p.open(
    #     format=pyaudio.paInt24,
    #     channels=in_channels,
    #     rate=samplerate,
    #     output_device_index=device_index,
    #     input=True,
    #     stream_callback=record_callback,
    # )

    out_stream = p.open(
        format=pyaudio.paInt24,
        channels=out_channels,
        rate=samplerate,
        output_device_index=device_index,
        output=True,
        stream_callback=play_callback,
    )

    # Keep the stream active for a few seconds
    print("Adjust the gain to ")
    try:
        while out_stream.is_active():
            pass
    except KeyboardInterrupt:
        pass

    # Clean up
    # in_stream.stop_stream()
    out_stream.stop_stream()
    # in_stream.close()
    out_stream.close()
    p.terminate()


if __name__ == "__main__":
    main()
