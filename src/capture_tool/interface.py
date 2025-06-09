import sounddevice as sd


class AudioInterface:
    device: int
    blocksize: int
    num_sends: int
    num_returns: int
    send_calibrated: bool
    return_calibrated: bool
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

        self.send_calibrated = config["send_level_dbu"] is not None
        self.return_calibrated = config["return_levels_dbu"] is not None

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
            "send_level_dbu": self.send_level_dbu if self.send_calibrated else None,
            "return_levels_dbu": self.return_levels_dbu if self.return_calibrated else None,
        }

    def set_send_calibrated(self, calibrated: bool = True):
        self.send_calibrated = calibrated

    def set_return_calibrated(self, calibrated: bool = True):
        self.return_calibrated = calibrated

    def set_send_level_dbu(
        self,
        measured_send_level_dbu: float,
        send_level_dbfs: float = 0.0,
    ):
        self.send_level_dbu = measured_send_level_dbu - send_level_dbfs

    def set_return_level_dbu(
        self,
        send_level_dbfs: float,
        return_level_dbfs: float,
        channel: int,
    ):
        send_level_dbu = self.send_dbfs_to_dbu(send_level_dbfs)
        self.return_levels_dbu[channel] = send_level_dbu - return_level_dbfs

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
