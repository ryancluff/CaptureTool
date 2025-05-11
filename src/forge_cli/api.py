import json
import requests


class ForgeApi:
    class Resource:
        TYPES = ["input", "session", "capture", "snapshot"]
        TYPES_PLURAL = [RESOURCE + "s" for RESOURCE in TYPES]

        def __init__(self, resource_type: str):
            if resource_type not in self.TYPES or resource_type not in self.TYPES_PLURAL:
                raise ValueError(
                    f"Invalid resource: {resource_type}. Must be one of {[type + '(s)' for type in self.TYPES]}"
                )
            self.type = resource_type + "s" if resource_type in self.TYPES else resource_type

    class File:
        TYPES = ["input", "capture"]

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

    def list(self, resource_type: str) -> list:
        resource = self.Resource(resource_type)
        return self._request("GET", f"{self.base_url}/{resource.type}/")

    def create(self, resource_type: str, config: dict) -> dict:
        resource = self.Resource(resource_type)
        return self._request("POST", f"{self.base_url}/{resource.type}/", data=config, status_code=201)

    def get(self, resource_type: str, resource_id: str) -> dict:
        resource = self.Resource(resource_type)
        return self._request("GET", f"{self.base_url}/{resource.type}/{resource_id}/")

    def update(self, resource_type: str, resource_id: str, config: dict) -> dict:
        resource = self.Resource(resource_type)
        return self._request("PATCH", f"{self.base_url}/{resource.type}/{resource_id}/", data=config)

    def delete(self, resource_type: str, resource_id: str) -> dict:
        resource = self.Resource(resource_type)
        return self._request("DELETE", f"{self.base_url}/{resource.type}/{resource_id}/")

    def upload(self, resource_type: str, resource_id: str, file_path: str) -> dict:
        resource = self.Resource(resource_type)
        with open(file_path, "rb") as fp:
            data = fp.read()
        return self._request("PATCH", f"{self.base_url}/{resource.type}/{resource_id}/", data=data)

    def download(self, resource_type: str, resource_id: str) -> bytes:
        resource = self.Resource(resource_type)
        response = requests.get(f"{self.base_url}/{resource.type}/{resource_id}/")
        if response.status_code != 200:
            raise Exception(f"Request failed: {response.status_code} {response.text}")
        return response.content
