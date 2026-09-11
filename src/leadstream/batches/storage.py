from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError


class ChunkedUpload(Protocol):
    name: str
    content_type: str | None

    def chunks(self, chunk_size: int | None = None) -> Iterable[bytes]: ...


@dataclass(frozen=True)
class StoredInput:
    backend: str
    key: str
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str


def _root() -> Path:
    root = Path(settings.BATCH_STORAGE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_key(key: str) -> Path:
    root = _root()
    candidate = (root / key).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValidationError("Chave de armazenamento inválida.")
    return candidate


def save_upload(*, tenant_id: object, upload: ChunkedUpload) -> StoredInput:
    original_name = Path(upload.name or "entrada.csv").name[:255]
    if not original_name.casefold().endswith(".csv"):
        raise ValidationError({"arquivo": "Envie um arquivo com extensão .csv."})
    key = f"{tenant_id}/{uuid.uuid4()}.csv"
    destination = _resolve_key(key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with destination.open("xb") as target:
            chunks = upload.chunks(1024 * 1024)
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ValidationError({"arquivo": "Conteúdo de upload inválido."})
                size += len(chunk)
                if size > settings.BATCH_MAX_UPLOAD_BYTES:
                    raise ValidationError(
                        {"arquivo": "Arquivo excede o limite configurado para upload."}
                    )
                digest.update(chunk)
                target.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if size == 0:
        destination.unlink(missing_ok=True)
        raise ValidationError({"arquivo": "O arquivo CSV está vazio."})
    return StoredInput(
        backend="LOCAL",
        key=key,
        original_name=original_name,
        content_type=upload.content_type or "text/csv",
        size_bytes=size,
        sha256=digest.hexdigest(),
    )


def open_input(key: str) -> BinaryIO:
    return _resolve_key(key).open("rb")


def delete_input(key: str) -> None:
    _resolve_key(key).unlink(missing_ok=True)


@dataclass(frozen=True)
class StoredExport:
    backend: str
    key: str
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str


def save_export_file(
    *,
    tenant_id: object,
    file_name: str,
    file_path: Path,
    content_type: str = "text/csv; charset=utf-8",
) -> StoredExport:
    import shutil

    from leadstream.integrations.appwrite import AppwriteConfig, AppwriteStorageClient

    size = file_path.stat().st_size
    digest = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()

    appwrite_config = AppwriteConfig.from_settings()
    if appwrite_config is not None:
        try:
            client = AppwriteStorageClient(appwrite_config)
            file_id = f"exp-{uuid.uuid4().hex[:28]}"
            with file_path.open("rb") as f:
                content = f.read()
            client.upload_file(
                bucket_id=settings.APPWRITE_STORAGE_BUCKET_EXPORTS,
                file_id=file_id,
                file_name=file_name,
                content=content,
                content_type=content_type,
            )
            return StoredExport(
                backend="APPWRITE",
                key=f"{settings.APPWRITE_STORAGE_BUCKET_EXPORTS}/{file_id}",
                file_name=file_name,
                content_type=content_type,
                size_bytes=size,
                sha256=sha256,
            )
        except (httpx.HTTPError, OSError, ValueError):
            # Fallback seguro para armazenamento local se Appwrite estiver indisponível
            pass

    rel_key = f"exports/{tenant_id}/{uuid.uuid4()}_{file_name}"
    dest = _resolve_key(rel_key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest)
    return StoredExport(
        backend="LOCAL",
        key=rel_key,
        file_name=file_name,
        content_type=content_type,
        size_bytes=size,
        sha256=sha256,
    )


def open_export(backend: str, key: str) -> BinaryIO | bytes:
    from leadstream.integrations.appwrite import AppwriteConfig, AppwriteStorageClient

    if backend == "APPWRITE":
        appwrite_config = AppwriteConfig.from_settings()
        if appwrite_config is not None:
            bucket_id, file_id = key.split("/", 1)
            client = AppwriteStorageClient(appwrite_config)
            return client.download_file(bucket_id=bucket_id, file_id=file_id)
    return _resolve_key(key).open("rb")


def delete_export(backend: str, key: str) -> None:
    from leadstream.integrations.appwrite import AppwriteConfig, AppwriteStorageClient

    if backend == "APPWRITE":
        appwrite_config = AppwriteConfig.from_settings()
        if appwrite_config is not None:
            bucket_id, file_id = key.split("/", 1)
            client = AppwriteStorageClient(appwrite_config)
            client.delete_file(bucket_id=bucket_id, file_id=file_id)
            return
    _resolve_key(key).unlink(missing_ok=True)
