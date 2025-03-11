import wavio

reamp = wavio.read("inputs/v3_0_0.wav")
wavio.write("v3_0_0_trim.wav", reamp.data[: reamp.rate * 10], reamp.rate, sampwidth=3)
