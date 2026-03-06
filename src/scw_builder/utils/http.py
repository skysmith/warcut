from __future__ import annotations

import json
import socket
import ssl
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None


def get_json(url: str, timeout: int = 30) -> dict:
    with open_url(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def open_url(url: str, timeout: int = 30, retries: int = 2, retry_delay: float = 0.75):
    request = Request(url, headers={"User-Agent": "warcut/0.1"})
    context = _ssl_context()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return urlopen(request, timeout=timeout, context=context)
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise RuntimeError(_ssl_guidance()) from exc
            if _is_retryable_network_error(reason) and attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                last_exc = exc
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("open_url failed without an exception")


def download_to_file(url: str, destination: Path, timeout: int = 60) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open_url(url, timeout=timeout) as response, destination.open("wb") as handle:
        handle.write(response.read())
    return destination


def dump_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _ssl_guidance() -> str:
    return (
        "HTTPS certificate verification failed. warcut tried the certifi CA bundle, "
        "but Python still could not verify the remote certificate. On macOS Python.org "
        "installs, run 'Install Certificates.command' once, then retry. If that still "
        "fails, confirm certifi is installed in the same Python environment."
    )


def _is_retryable_network_error(reason: object) -> bool:
    if isinstance(reason, socket.gaierror):
        return True
    if isinstance(reason, TimeoutError):
        return True
    message = str(reason).lower()
    return any(
        marker in message
        for marker in [
            "temporary failure in name resolution",
            "nodename nor servname provided",
            "name or service not known",
            "timed out",
        ]
    )
