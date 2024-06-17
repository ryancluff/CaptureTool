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

    with wave.open(sys.argv[1], "rb") as play_wf:
        with wave.open(sys.argv[2], "wb") as record_wf:
            # Define callback for playback (1)
            def play_callback(in_data, frame_count, time_info, status):
                data = play_wf.readframes(frame_count)
                # If len(data) is less than requested frame_count, PyAudio automatically
                # assumes the stream is finished, and the stream stops.
                return (data, pyaudio.paContinue)
            
            # Instantiate PyAudio and initialize PortAudio system resources
            p = pyaudio.PyAudio()

            # # Get the host APIs
            host_api_count = p.get_host_api_count()
            for i in range(host_api_count):
                host_api_info = p.get_host_api_info_by_index(i)
                print(f'Host API {i}: {host_api_info["name"]}')

            # Get the devices
            device_count = p.get_device_count()
            for i in range(device_count):
                device_info = p.get_device_info_by_index(i)
                print(f'Device {i}: {device_info["name"]}')
                print(f'  Input channels: {device_info["maxInputChannels"]}')
                print(f'  Output channels: {device_info["maxOutputChannels"]}')
            print("\n")

            # Get the defaults
            host_api_info = p.get_default_host_api_info()
            output_device_info = p.get_default_output_device_info()
            input_device_info = p.get_default_input_device_info()
            print(f'Default host API: {host_api_info["name"]}')
            print(f'Default output device: {output_device_info["name"]}')
            print(f'Default input device: {input_device_info["name"]}')

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

            # Release PortAudio system resources
            p.terminate()