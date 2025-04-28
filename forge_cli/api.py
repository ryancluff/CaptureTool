import json
from pathlib import Path
import requests

from capture_tool.util import hash


class Resource:
    def __init__(self, config):
        self.config = config
        self.id = None

    def __str__(self):
        return json.dumps(self.config, indent=4)


class ForgeInput(Resource):
    pass


class ForgeSession(Resource):
    pass


class ForgeCapture(Resource):
    pass


class ForgeApi:
    def __init__(self, config: dict = {}):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8000)
        self.protocol = config.get("protocol", "http")
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"

    def _request(
        self,
        method: str,
        url: str,
        data: dict | bytes | None = None,
        status_code: int = 200,
    ) -> dict:
        if isinstance(data, bytes):
            headers = {
                "Content-Type": "audio/wav",
                "Content-Disposition": "attachment; filename=upload.wav",
            }
        else:
            headers = {
                "Content-Type": "application/json",
            }
            data = json.dumps(data) if data else None
        response = requests.request(method, url, headers=headers, data=data)
        if response.status_code != status_code:
            raise Exception(f"Request failed: {method} {url} {response.status_code} {response.text}")
        if not response.content:
            return {}
        return response.json()

    def _get(self, url: str) -> dict:
        return self._request("GET", url)

    def _post(self, url: str, data: dict) -> dict:
        return self._request("POST", url, data=data, status_code=201)

    def _patch(self, url: str, data: dict | bytes) -> dict:
        return self._request("PATCH", url, data=data)

    def _delete(self, url: str) -> dict:
        return self._request("DELETE", url)

    def list_inputs(self) -> list:
        return self._get(f"{self.base_url}/inputs/")

    def list_sessions(self) -> list:
        return self._get(f"{self.base_url}/sessions/")

    def list_captures(self) -> list:
        return self._get(f"{self.base_url}/captures/")

    def get_input(self, input_id: str) -> dict:
        return self._get(f"{self.base_url}/inputs/{input_id}/")

    def get_session(self, session_id: str) -> dict:
        return self._get(f"{self.base_url}/sessions/{session_id}/")

    def get_capture(self, capture_id: str) -> dict:
        return self._get(f"{self.base_url}/captures/{capture_id}/")

    def create_input(self, config: dict) -> dict:
        return self._post(f"{self.base_url}/inputs/", config)

    def create_session(self, config: dict) -> dict:
        return self._post(f"{self.base_url}/sessions/", config)

    def create_capture(self, config: dict) -> dict:
        return self._post(f"{self.base_url}/captures/", config)

    def update_input(self, input_id: str, config: dict) -> dict:
        return self._patch(f"{self.base_url}/inputs/{input_id}/", config)

    def update_session(self, session_id: str, config: dict) -> dict:
        return self._patch(f"{self.base_url}/sessions/{session_id}/", config)

    def update_capture(self, capture_id: str, config: dict) -> dict:
        return self._patch(f"{self.base_url}/captures/{capture_id}/", config)

    def upload_input(self, input_id: str, file_path: str):
        with open(file_path, "rb") as fp:
            data = fp.read()
        return self._patch(f"{self.base_url}/inputs/{input_id}/", data=data)

    def upload_capture(self, capture_id: str, file_path: str):
        with open(file_path, "rb") as fp:
            data = fp.read()
        return self._patch(f"{self.base_url}/captures/{capture_id}/", data=data)

    def delete_input(self, input_id: str):
        return self._delete(f"{self.base_url}/inputs/{input_id}/")

    def delete_session(self, session_id: str):
        return self._delete(f"{self.base_url}/sessions/{session_id}/")

    def delete_capture(self, capture_id: str):
        return self._delete(f"{self.base_url}/captures/{capture_id}/")
