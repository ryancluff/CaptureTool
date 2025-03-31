import json
from pathlib import Path
import requests

from capture_tool.util import hash


class ForgeApi:
    def __init__(self, config):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8000)
        self.protocol = config.get("protocol", "http")
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"

    def _post_json(self, url: str, payload: dict) -> str:
        headers = {
            "Content-Type": "application/json",
        }
        payload = json.dumps(payload)
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code != 201:
            raise Exception(f"Failed to post json: {url} {response.status_code} {response.text}")
        return response.json().get("id")

    def _post_wav(self, url: str, path: Path) -> None:
        headers = {
            "Content-Disposition": "attachment; filename=upload.wav",
            "Content-Type": "audio/wav",
        }
        with open(path, "rb") as fp:
            response = requests.request("POST", url, headers=headers, data=fp.read())
        if response.status_code != 201:
            raise Exception(f"Failed to post wav: {url} {response.status_code} {response.text}")

    def post_input(self, input: dict):
        if not input.get("path"):
            raise ValueError("Input must have a path")
        input["file_hash"] = hash(input["path"])

        url = f"{self.base_url}/inputs/"
        id = self._post_json(url, input)

        url = f"{self.base_url}/inputs/{id}/file"
        self._post_wav(url, input.path)
        return id
