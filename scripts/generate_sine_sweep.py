import matplotlib.pyplot as plt
import wavio

from core.wave import SweepWave


if __name__ == "__main__":
    start_freq = 20
    end_freq = 20000
    duration = 10
    sample_rate = 48000
    dbfs = 0

    w = SweepWave(
        start_freq,
        end_freq,
        duration,
        sample_rate,
        dbfs
    )
    wavio.write("sine_sweep.wav", w.audio, sample_rate, sampwidth=3)
