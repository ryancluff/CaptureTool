import sounddevice as sd


class AudioInterface:
    device: int
    blocksize: int
    num_sends: int
    num_returns: int
    _send_calibrated: bool
    _return_calibrated: bool
    send_level_dbu: float
    return_levels_dbu: list[float]

    INIT_SETTINGS = {
        "device": sd.default.device[1],
        "blocksize": 512,
        "send_channel": 1,
        "return_channels": 1,
        "send_level_dbu": None,
        "return_levels_dbu": None,
    }

    class ClipException(Exception):
        def __init__(self, channel, dbfs):
            self.channel = channel
            self.dbfs = dbfs
            self.message = f"peak level of {dbfs} dBFS on channel {channel} exceeds 0 dBFS"
            super().__init__(self.message)

    def __init__(self, config: dict):
        self.device = config["device"]
        self.blocksize = config["blocksize"]
        self.num_sends = config["send_channel"]
        self.num_returns = config["return_channels"]

        self._send_calibrated = config["send_level_dbu"] is not None
        self._return_calibrated = config["return_levels_dbu"] is not None

        # calibration values
        # the level (dBu) being sent from the interface to the gear corresponding to a 1kHz sine wave with 0dBFS peak
        self.send_level_dbu = config.get("send_level_dbu", 0.0)
        # an array of levels like above that correspond to the return channels
        self.return_levels_dbu = config.get("return_levels_dbu", [0.0 for _ in range(self.num_returns)])

    def get_config(self) -> dict:
        return {
            "device": self.device,
            "blocksize": self.blocksize,
            "send_channel": self.num_sends,
            "return_channels": self.num_returns,
            "send_level_dbu": self.send_level_dbu if self._send_calibrated else None,
            "return_levels_dbu": self.return_levels_dbu if self._return_calibrated else None,
        }

    def set_send_level_dbu(
        self,
        measured_send_level_dbu: float,
        send_level_dbfs: float = 0.0,
    ):
        self._send_calibrated = True
        self.send_level_dbu = measured_send_level_dbu - send_level_dbfs

    def set_return_levels_dbu(
        self,
        send_level_dbfs: float,
        return_levels_dbfs: list[float],
    ):
        self._return_calibrated = True
        send_level_dbu = self.send_dbfs_to_dbu(send_level_dbfs)
        for channel in range(self.num_returns):
            self.return_levels_dbu[channel] = send_level_dbu - return_levels_dbfs[channel]

    # Convert send level dBu to dBFS
    def send_dbu_to_dbfs(self, send_level_dbu: float) -> float:
        if self.send_level_dbu is None:
            raise RuntimeError("send levels not set. exitting...")
        return send_level_dbu - self.send_level_dbu

    # Convert send level dBFS to dBu
    def send_dbfs_to_dbu(self, send_level_dbfs: float) -> float:
        if self.send_level_dbu is None:
            raise RuntimeError("send levels not set. exitting...")
        return send_level_dbfs + self.send_level_dbu

    # Convert return level dBu to dBFS for the given channel
    def return_dbu_to_dbfs(
        self,
        return_level_dbu: float,
        channel: int,
    ) -> float:
        if self.return_levels_dbu is None:
            raise RuntimeError("return levels not set. exitting...")
        return return_level_dbu - self.return_levels_dbu[channel - 1]

    # Convert return level dBFS to dBu for the given channel
    def return_dbfs_to_dbu(
        self,
        return_level_dbfs: float,
        channel: int,
    ) -> float:
        if self.return_levels_dbu is None:
            raise RuntimeError("return levels not set. exitting...")
        return return_level_dbfs + self.return_levels_dbu[channel - 1]

    # Convert floating-point audio data to 24-bit data
    @classmethod
    def pack(cls, data: np.ndarray) -> bytes:
        return b"".join(
            int(sample).to_bytes(
                3,
                byteorder="little",
                signed=True,
            )
            for sample in data.flatten()
        )

    # Convert 24-bit data to floating-point audio data
    @classmethod
    def unpack(cls, data: bytes, channels: int) -> np.ndarray:
        return np.array(
            [
                int.from_bytes(
                    data[i : i + 3],
                    byteorder="little",
                    signed=True,
                )
                for i in range(0, len(data), 3)
            ],
            dtype=np.int32,
        ).reshape((-1, channels))

    def get_send_calibration_stream(
        self,
        send_level_dbfs: float = -3.0,
    ) -> sd.RawOutputStream:
        sine_wave = SineWave(self.frequency, self.samplerate, send_level_dbfs)

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            output = np.zeros((frames, self.num_sends), dtype=np.int32)
            output[:, self.channels["reamp"] - 1] = sine_wave.of_length(samples=frames)
            outdata[:] = self.pack(output)

        stream = sd.RawOutputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=self.num_sends,
            dtype="int24",
            callback=callback,
        )

        return stream

    def get_return_calibration_stream(
        self,
        send_level_dbfs: float = -3.0,
    ) -> tuple[sd.RawStream, np.array, threading.Event]:
        frame = 0
        sine_wave = SineWave(self.frequency, self.samplerate, send_level_dbfs).of_length(seconds=2)
        peak_levels = np.zeros(self.num_returns, dtype=np.int32)
        done = threading.Event()

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal frame
            chunksize = min(len(sine_wave) - frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_sends))
            output[:chunksize, self.channels["reamp"] - 1] = sine_wave[frame : frame + chunksize].flatten()
            outdata[:] = self.pack(output)

            levels = np.max(np.abs(self.unpack(indata, self.num_returns)), axis=0)
            for i in range(self.num_returns):
                if levels[i] > peak_levels[i]:
                    peak_levels[i] = levels[i]

            # increment the frame count and stop if the end of the clip is reached
            frame += frames
            if frame >= len(sine_wave):
                raise sd.CallbackStop()

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_returns, self.num_sends),
            dtype="int24",
            callback=callback,
            finished_callback=done.set,
        )

        return stream, peak_levels, done

    def get_capture_stream(
        self,
    ) -> tuple[
        sd.RawStream,
        callable,
        np.array,
        np.array,
        np.array,
        threading.Event,
    ]:
        frame = 0
        # scale the reamp data using the reamp delta to output at the proper level
        send_audio = np.array(self.wav.data * db_to_scalar(0 - self.send_level_dbu), dtype=np.int32)
        # append 10 blocks of zeros to the end of the return data to account for latency
        return_audio = np.zeros((len(send_audio) + 10 * self.blocksize, self.num_returns), dtype=np.int32)
        peak_levels = np.zeros(self.num_returns, dtype=np.int32)
        done = threading.Event()

        def get_frame() -> int:
            return frame

        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal frame
            chunksize = min(len(send_audio) - frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_sends))
            output[:chunksize, self.channels["reamp"] - 1] = send_audio[frame : frame + chunksize].flatten()
            outdata[:] = self.pack(output)

            # read the recording data from the interface return channels
            input = self.unpack(indata, self.num_returns)
            return_audio[frame : frame + frames] = input

            levels = np.max(np.abs(input), axis=0)
            for i in range(self.num_returns):
                if levels[i] > peak_levels[i]:
                    peak_levels[i] = levels[i]

            frame += frames
            if frame >= len(send_audio):
                raise sd.CallbackStop()

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_returns, self.num_sends),
            dtype="int24",
            callback=callback,
            finished_callback=done.set,
        )

        return (
            stream,
            get_frame,
            send_audio,
            return_audio,
            peak_levels,
            done,
        )

    def get_testtone_stream(
        self,
        output_level: float,
        unit: TestToneStream.TestToneUnit = TestToneStream.TestToneUnit.DBFS,
    ) -> tuple[sd.RawOutputStream, callable, callable, callable]:
        if unit == TestToneStream.TestToneUnit.DBFS and output_level > 0.0:
            raise ValueError("output level must be negative for dbfs test tone")

        def get_output_level_dbfs():
            if unit == TestToneStream.TestToneUnit.DBFS:
                return output_level
            elif unit == TestToneStream.TestToneUnit.DBU:
                return self.send_dbfs_to_dbu(output_level)

        sine_wave = SineWave(dbfs=get_output_level_dbfs())

        def increase_output_level():
            nonlocal output_level
            output_level += 1
            nonlocal sine_wave
            sine_wave = SineWave(self.frequency, self.samplerate, get_output_level_dbfs())

        def decrease_output_level():
            nonlocal output_level
            output_level -= 1
            nonlocal sine_wave
            sine_wave = SineWave(self.frequency, self.samplerate, get_output_level_dbfs())

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            output = np.zeros((frames, self.num_sends), dtype=np.int32)
            output[:, self.channels["reamp"] - 1] = sine_wave.of_length(samples=frames)
            outdata[:] = self.pack(output)

        stream = sd.RawOutputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=self.num_sends,
            dtype="int24",
            callback=callback,
        )

        return stream, get_output_level_dbfs, increase_output_level, decrease_output_level

    def reamp(self):
        if self.send_level_dbu is None:
            raise RuntimeError("reamp not calibrated. exitting...")

        # scale the reamp data using the reamp delta to output at the proper level
        reamp_audio = np.array(self.wav.data * db_to_scalar(0 - self.send_level_dbu), dtype=np.int32)

        current_frame = 0
        recording_done = threading.Event()

        def callback(outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            nonlocal current_frame
            chunksize = min(len(reamp_audio) - current_frame, frames)

            # write the reamp data to the interface output channel
            output = np.zeros((frames, self.num_sends))
            output[:chunksize, self.channels["reamp"] - 1] = reamp_audio[
                current_frame : current_frame + chunksize
            ].flatten()
            outdata[:] = self.pack(output)

            current_frame += frames
            if current_frame >= len(reamp_audio):
                raise sd.CallbackStop()

        stream = sd.RawOutputStream(
            samplerate=self.wav.rate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_returns, self.num_sends),
            dtype="int24",
            callback=callback,
            finished_callback=recording_done.set,
        )

        with stream:
            while not recording_done.wait(timeout=1.0):
                current_seconds = current_frame // self.wav.rate
                current_seconds = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
                total_seconds = len(self.wav.data) // self.wav.rate
                total_seconds = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
                print(f"{current_seconds} / {total_seconds}")

    def passthrough(self):
        def callback(indata, outdata, frames, time, status):
            if status:
                print(status, file=sys.stderr)

            outdata[:] = indata

        stream = sd.RawStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            device=self.device,
            channels=(self.num_returns, self.num_sends),
            dtype="int24",
            callback=callback,
        )

        try:
            with stream:
                print("press ctrl+c to stop")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
