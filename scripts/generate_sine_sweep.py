import matplotlib.pyplot as plt
import wavio

from capture_tool.wave import SweepWave


if __name__ == "__main__":
    start_freq = 20
    end_freq = 20000
    duration = 5
    sample_rate = 48000
    dbfs = -0.1

    w = SweepWave(
        start_freq=start_freq,
        end_freq=end_freq,
        duration=duration,
        samplerate=sample_rate,
        dbfs=dbfs,
        loop=False,
    )
    wavio.write("sine_sweep.wav", w.audio, sample_rate, sampwidth=3)
