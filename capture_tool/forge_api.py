import json
from pathlib import Path
import requests

from capture_tool.util import hash


class ForgeInput:
    def __init__(self, config):
        self.config = config
        self.id = None


class ForgeSession:
    def __init__(self, config):
        self.config = config
        self.id = None


class ForgeCapture:
    def __init__(self, config):
        self.config = config
        self.id = None


class ForgeApi:
    def __init__(self, config: dict = {}):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8000)
        self.protocol = config.get("protocol", "http")
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"

    def _get(self, url: str) -> dict:
        method = "GET"
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.request(method, url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Request failed: {method} {url} {response.status_code} {response.text}")
        return response.json()

    def _post_json(self, url: str, payload: dict) -> str:
        method = "POST"
        headers = {
            "Content-Type": "application/json",
        }
        payload = json.dumps(payload)
        response = requests.request(method, url, headers=headers, data=payload)
        if response.status_code != 201:
            raise Exception(f"Request failed: {method} {url} {response.status_code} {response.text}")
        return response.json().get("id")

    def _post_wav(self, url: str, path: Path) -> None:
        method = "POST"
        headers = {
            "Content-Disposition": "attachment; filename=upload.wav",
            "Content-Type": "audio/wav",
        }
        with open(path, "rb") as fp:
            response = requests.request(method, url, headers=headers, data=fp.read())
        if response.status_code != 201:
            raise Exception(f"File upload failed: {method} {url} {response.status_code} {response.text}")

    def list_inputs(self):
        url = f"{self.base_url}/inputs/"
        return self._get(url)

    def post_input(self, input: ForgeInput):
        path = input.config.get("path")
        if not path:
            raise ValueError("Input must have a path")
        input["file_hash"] = hash(path)

        url = f"{self.base_url}/inputs/"
        id = self._post_json(url, input)

        url = f"{self.base_url}/inputs/{id}/file"
        self._post_wav(url, path)
        return id

    def list_sessions(self):
        url = f"{self.base_url}/sessions/"
        return self._get(url)

    def get_session(self, session_id: str):
        url = f"{self.base_url}/sessions/{session_id}/"
        return self._get(url)

    def post_session(self, session: ForgeSession):
        url = f"{self.base_url}/sessions/"
        return self._post_json(url, session.config)

    def list_captures(self):
        url = f"{self.base_url}/captures/"
        return self._get(url)

    def get_captures(self, capture_id: str):
        url = f"{self.base_url}/captures/{capture_id}/"
        return self._get(url)
