import numpy as np
from numpy import typing as npt
from pathlib import Path
import wavio

from core.util import read_config


class CaptureManifest:
    capture_id: int
    session_id: int
    input_id: str
    parameters: dict
    switches: dict
    channels: list[str]
    level_dbu: float

    output_dir: Path
    input_path: Path
    input_data: npt.NDArray[np.int32]
    samplerate: int

    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        elif not path.is_dir():
            path = Path(path, "manifest.json")

        config = read_config(path)
        self.capture_id = config["capture_id"]
        self.session_id = config["session_id"]
        self.input_id = config["input_id"]
        self.parameters = config.get("parameters", {})
        self.switches = config.get("switches", {})
        self.channels = config.get("channels", [])
        self.level_dbu = config["level_dbu"]

        self.output_dir = path.parent
        self.input_path = Path(self.output_dir.parent, "inputs", self.input_id)

        input_wav = wavio.read(self.input_path)
        self.input_data = input_wav.data
        self.samplerate = input_wav.rate
