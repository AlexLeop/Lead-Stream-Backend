from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, Self, cast

import httpx
from django.conf import settings

from leadstream.common.health import HealthResult


@dataclass(frozen=True, slots=True)
class AppwriteConfig:
    endpoint: str
    project_id: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 3.0

    @classmethod
    def from_settings(cls) -> Self | None:
        values = (
            settings.APPWRITE_ENDPOINT,
            settings.APPWRITE_PROJECT_ID,
            settings.APPWRITE_API_KEY,
        )
        if not all(values):
            return None
        return cls(
            endpoint=str(settings.APPWRITE_ENDPOINT).rstrip("/"),
            project_id=str(settings.APPWRITE_PROJECT_ID),
            api_key=str(settings.APPWRITE_API_KEY),
            timeout_seconds=float(settings.APPWRITE_TIMEOUT_SECONDS),
        )


class AppwriteHealthClient(Protocol):
    def check(self) -> None: ...


class HttpAppwriteHealthClient:
    def __init__(self, config: AppwriteConfig) -> None:
        self._config = config

    def check(self) -> None:
        headers = {
            "X-Appwrite-Project": self._config.project_id,
            "X-Appwrite-Key": self._config.api_key,
        }
        with httpx.Client(
            timeout=self._config.timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = client.get(f"{self._config.endpoint}/health", headers=headers)
            response.raise_for_status()


def diagnose_appwrite(
    client_factory: Callable[[AppwriteConfig], AppwriteHealthClient] = HttpAppwriteHealthClient,
) -> HealthResult:
    config = AppwriteConfig.from_settings()
    if config is None:
        return HealthResult("degraded")
    try:
        client_factory(config).check()
    except httpx.HTTPError:
        return HealthResult("unavailable")
    except (OSError, ValueError):
        return HealthResult("unavailable")
    return HealthResult("ok")


class AppwriteStorageClient:
    def __init__(self, config: AppwriteConfig) -> None:
        self._config = config

    def upload_file(
        self,
        *,
        bucket_id: str,
        file_id: str,
        file_name: str,
        content: bytes,
        content_type: str = "text/csv; charset=utf-8",
    ) -> dict[str, Any]:
        headers = {
            "X-Appwrite-Project": self._config.project_id,
            "X-Appwrite-Key": self._config.api_key,
        }
        url = f"{self._config.endpoint}/storage/buckets/{bucket_id}/files"
        data = {"fileId": file_id}
        files = {"file": (file_name, content, content_type)}
        with httpx.Client(timeout=self._config.timeout_seconds * 5) as client:
            response = client.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    def download_file(self, *, bucket_id: str, file_id: str) -> bytes:
        headers = {
            "X-Appwrite-Project": self._config.project_id,
            "X-Appwrite-Key": self._config.api_key,
        }
        url = f"{self._config.endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download"
        with httpx.Client(timeout=self._config.timeout_seconds * 5) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.content

    def delete_file(self, *, bucket_id: str, file_id: str) -> None:
        headers = {
            "X-Appwrite-Project": self._config.project_id,
            "X-Appwrite-Key": self._config.api_key,
        }
        url = f"{self._config.endpoint}/storage/buckets/{bucket_id}/files/{file_id}"
        with httpx.Client(timeout=self._config.timeout_seconds * 2) as client:
            response = client.delete(url, headers=headers)
            if response.status_code != 404:
                response.raise_for_status()
