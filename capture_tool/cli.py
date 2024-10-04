import json
from argparse import ArgumentParser
from pathlib import Path
from sounddevice import query_devices


from capture_tool.util import timestamp
# from capture_tool.capture import capture
# from capture_tool.calibrate import calibrate


def _capture_tool(interface_config: dict, calibration_config: dict, capture_config: dict, outdir: Path):
    if not outdir.exists():
        raise RuntimeError(f"No output location found at {outdir}")
    
    # Write
    for basename, config in (
        ("device", interface_config),
        ("calibration", calibration_config),
        ("capture", capture_config),
    ):
        with open(Path(outdir, f"config_{basename}.json"), "w") as fp:
            json.dump(config, fp, indent=4)

    output_level = calibrate(
        settings.device,
        settings.output_channel,
        settings.input_channels,
        settings.target_dbu,
        frequency=settings.frequency,
        blocksize=settings.calibration_blocksize,
        samplerate=settings.calibration_samplerate,
    )

    capture(
        settings.device,
        settings.output_channel,
        settings.input_channels,
        settings.reamp_file,
        output_level,
        blocksize=settings.capture_blocksize,
    )


def capture_tool():
    parser = ArgumentParser(description="Capture tool")

    parser.add_argument("interface_config_path", type=str)
    parser.add_argument("capture_config_path", type=str)    
    parser.add_argument("outdir")
    
    args = parser.parse_args()
    
    def ensure_outdir(outdir: str) -> Path:
        outdir = Path(outdir, timestamp())
        outdir.mkdir(parents=True, exist_ok=False)
        return outdir

    outdir = ensure_outdir(args.outdir)
    with open(args.device_config_path, "r") as fp:
        interface_config = json.load(fp)
    with open(args.capture_config_path, "r") as fp:
        capture_config = json.load(fp)
    
    _capture_tool(interface_config, capture_config, outdir)



if __name__ == "__main__":
    capture_tool()
