import json
import requests


class ForgeApi:
    DEFAUT_HEADERS = {
        "Content-Type": "application/json",
    }

    class Resource:
        TYPES = ["input", "session", "capture", "file", "snapshot"]
        TYPES_PLURAL = [RESOURCE + "s" for RESOURCE in TYPES]

        def __init__(self, resource_type: str):
            if resource_type not in self.TYPES and resource_type not in self.TYPES_PLURAL:
                raise ValueError(
                    f"Invalid resource: {resource_type}. Must be one of {[type + '(s)' for type in self.TYPES]}"
                )
            self.type = resource_type + "s" if resource_type in self.TYPES else resource_type

    class File:
        TYPES = ["input", "file"]

    class StatusException(Exception):
        def __init__(self, method: str, url: str, status_code: int, text: str):
            self.method = method
            self.url = url
            self.status_code = status_code
            self.text = text

        def __str__(self):
            return f"Request failed: {self.method} {self.url} {self.status_code} {self.text}"

    def __init__(self, api_str: str):
        self.api_str = api_str

    def list(self, resource_type: str) -> list:
        resource = self.Resource(resource_type)
        method = "GET"
        url = f"{self.api_str}/{resource.type}/"
        response = requests.request(method, url)
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: list = response.json()
        return result

    def create(self, resource_type: str, config: dict) -> dict:
        resource = self.Resource(resource_type)
        method = "POST"
        url = f"{self.api_str}/{resource.type}/"
        response = requests.request(method, url, headers=self.DEFAUT_HEADERS, data=json.dumps(config))
        if response.status_code != 201:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: dict = response.json()
        return result

    def get(self, resource_type: str, resource_id: str) -> dict:
        resource = self.Resource(resource_type)
        method = "GET"
        url = f"{self.api_str}/{resource.type}/{resource_id}/"
        response = requests.request(method, url)
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: dict = response.json()
        return result

    def update(self, resource_type: str, resource_id: str, config: dict) -> dict:
        resource = self.Resource(resource_type)
        method = "PATCH"
        url = f"{self.api_str}/{resource.type}/{resource_id}/"
        response = requests.request(method, url, headers=self.DEFAUT_HEADERS, data=json.dumps(config))
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: dict = response.json()
        return result

    def delete(self, resource_type: str, resource_id: str) -> dict:
        resource = self.Resource(resource_type)
        method = "DELETE"
        url = f"{self.api_str}/{resource.type}/{resource_id}/"
        response = requests.request(method, url)
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: dict = response.json()
        return result

    def upload(self, resource_type: str, resource_id: str, file_path: str) -> dict:
        with open(file_path, "rb") as fp:
            data = fp.read()
        resource = self.Resource(resource_type)
        method = "PATCH"
        url = f"{self.api_str}/{resource.type}/{resource_id}/"
        headers = {
            "Content-Type": "audio/wav",
            "Content-Disposition": "attachment; filename=upload.wav",
        }
        response = requests.request(method, url, headers=headers, data=data)
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, response.text)
        result: dict = response.json()
        return result

    def download(self, resource_type: str, resource_id: str) -> bytes:
        resource = self.Resource(resource_type)
        method = "GET"
        url = f"{self.api_str}/{resource.type}/{resource_id}/"
        response = requests.request(method, url)
        if response.status_code != 200:
            raise self.StatusException(method, url, response.status_code, "")
        result = response.content
        return result
