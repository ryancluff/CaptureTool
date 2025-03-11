import matplotlib.pyplot as plt
import numpy as np
import wavio


input_wav = wavio.read("inputs/v3_0_0_trimmed.wav")
input_data = input_wav.data[:, 0] / np.max(np.abs(input_wav.data))

output_wav = wavio.read("captures/2025-02-26-18-15-44/recording-instrument.wav")
output_data = -1 * output_wav.data[:, 0] / np.max(np.abs(output_wav.data))

cross_corr = np.correlate(input_data, output_data, mode="full")
delay = len(output_data) - np.argmax(cross_corr) - 1
print(f"Delay: {delay}")

output_data_corrected = np.zeros(len(output_data))
output_data_corrected[:-delay] = output_data[delay:]

plt.figure(figsize=(16, 5))
plt.plot(input_data, label="input")
plt.plot(output_data, linestyle="--", label="output")
plt.plot(output_data_corrected, linestyle="-.", label="corrected output")
plt.title(f"delay={delay}")
plt.legend()
plt.show()
