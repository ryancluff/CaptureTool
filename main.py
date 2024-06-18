import wave
import sys

import pyaudio

def convert(data, sampleSize = 4, channel = 0):
    for i in range(0, len(data), 2*sampleSize):
        for j in range(0, sampleSize):
           data[i + j + sampleSize * channel] = data[i + j + sampleSize * (1 - channel)]

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Plays a wave file. Usage: {sys.argv[0]} playback.wav record.wav")
        sys.exit(-1)

    play_wf = wave.open(sys.argv[1], "rb")
    record_wf = wave.open(sys.argv[2], "wb")

    # Define callback for playback (1)
    def play_callback(in_data, frame_count, time_info, status):
        data = play_wf.readframes(frame_count)
        # If len(data) is less than requested frame_count, PyAudio automatically
        # assumes the stream is finished, and the stream stops.
        return (data, pyaudio.paContinue)
    
    # Instantiate PyAudio and initialize PortAudio system resources
    p = pyaudio.PyAudio()

    record_wf.setnchannels(play_wf.getnchannels())
    record_wf.setsampwidth(play_wf.getsampwidth())
    record_wf.setframerate(play_wf.getframerate())

    record_stream = p.open(
        format=p.get_format_from_width(play_wf.getsampwidth()),
        channels=play_wf.getnchannels(),
        rate=play_wf.getframerate(),
        input=True,
    )

    play_stream = p.open(
        format=p.get_format_from_width(play_wf.getsampwidth()),
        channels=play_wf.getnchannels(),
        rate=play_wf.getframerate(),
        output=True,
        stream_callback=play_callback,
    )

    # Wait for stream to finish
    print('Recording...')
    while play_stream.is_active():
        data = record_stream.read(128)
        record_wf.writeframes(data)
    print('Done')

    # Close the streams
    record_stream.close()
    play_stream.close()

    # Close the wave files
    play_wf.close()
    record_wf.close()

    # Release PortAudio system resources
    p.terminate()