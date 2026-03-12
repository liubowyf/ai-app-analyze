"""Android proxy baseline helpers for the redroid runtime."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_RESIDUAL_CAPTURE_PROXY_PATTERN = re.compile(r"^(127\.0\.0\.1|localhost):(18|25|39)\d{3}$", re.IGNORECASE)
_PROXY_ENDPOINT_PATTERN = re.compile(r"^[^:\s]+:\d+$")
_ANDROID_PROXY_BASELINE_ENV_KEYS = (
    "ANDROID_HTTP_PROXY_BASELINE",
    "EMULATOR_HTTP_PROXY_BASELINE",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
)


def _normalize_proxy_value(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip()
    if normalized.lower() in {"", ":0", "null", "none"}:
        return None
    return normalized


def _normalize_proxy_endpoint(value: Optional[str]) -> Optional[str]:
    normalized = _normalize_proxy_value(value)
    if not normalized:
        return None
    if _PROXY_ENDPOINT_PATTERN.match(normalized):
        return normalized

    try:
        parsed = urlparse(normalized if "://" in normalized else f"http://{normalized}")
    except Exception:
        return None

    if parsed.hostname and parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return None


def _resolve_android_proxy_baseline_from_env() -> Optional[str]:
    for key in _ANDROID_PROXY_BASELINE_ENV_KEYS:
        value = os.getenv(key)
        if not value:
            continue
        normalized = _normalize_proxy_endpoint(value)
        if not normalized:
            logger.warning("Ignoring invalid Android proxy baseline env %s=%s", key, value)
            continue
        if _RESIDUAL_CAPTURE_PROXY_PATTERN.match(normalized):
            logger.warning("Ignoring residual capture proxy baseline env %s=%s", key, normalized)
            continue
        return normalized
    return None


def _is_residual_capture_proxy(proxy_value: Optional[str]) -> bool:
    normalized = _normalize_proxy_value(proxy_value)
    return bool(normalized and _RESIDUAL_CAPTURE_PROXY_PATTERN.match(normalized))


def _read_android_proxy(runner: Any, emulator_host: str, emulator_port: int) -> Optional[str]:
    return _normalize_proxy_value(
        runner.execute_adb_remote(
            emulator_host,
            emulator_port,
            "shell settings get global http_proxy",
        )
    )


def _write_android_proxy(
    runner: Any,
    emulator_host: str,
    emulator_port: int,
    proxy_value: Optional[str],
) -> None:
    command = (
        f"shell settings put global http_proxy {proxy_value}"
        if proxy_value
        else "shell settings put global http_proxy :0"
    )
    runner.execute_adb_remote(emulator_host, emulator_port, command)


def preflight_android_proxy_before_install(
    emulator_host: str,
    emulator_port: int,
    runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Verify emulator proxy state before installing a new APK.

    Residual localhost capture proxies are restored to the configured baseline proxy,
    or cleared when no baseline is configured.
    """
    if runner is None:
        from modules.android_runner import AndroidRunner

        runner = AndroidRunner()

    before_proxy = _read_android_proxy(runner, emulator_host, emulator_port)
    logger.info(
        "Android proxy preflight before install on %s:%s -> %s",
        emulator_host,
        emulator_port,
        before_proxy or "<cleared>",
    )

    action = "none"
    baseline_proxy = _resolve_android_proxy_baseline_from_env()
    expected_proxy = before_proxy

    if _is_residual_capture_proxy(before_proxy):
        action = "restore_baseline_proxy" if baseline_proxy else "clear_residual_proxy"
        expected_proxy = baseline_proxy
        logger.warning(
            "Detected residual Android capture proxy before install on %s:%s -> %s",
            emulator_host,
            emulator_port,
            before_proxy,
        )
        _write_android_proxy(runner, emulator_host, emulator_port, baseline_proxy)

    after_proxy = _read_android_proxy(runner, emulator_host, emulator_port)
    logger.info(
        "Android proxy preflight action on %s:%s -> %s",
        emulator_host,
        emulator_port,
        action,
    )
    logger.info(
        "Android proxy preflight after install on %s:%s -> %s",
        emulator_host,
        emulator_port,
        after_proxy or "<cleared>",
    )

    if _is_residual_capture_proxy(before_proxy):
        if after_proxy != expected_proxy or _is_residual_capture_proxy(after_proxy):
            raise RuntimeError(
                "Android proxy preflight failed for "
                f"{emulator_host}:{emulator_port}: before={before_proxy or '<cleared>'}, "
                f"action={action}, after={after_proxy or '<cleared>'}, "
                f"expected={expected_proxy or '<cleared>'}"
            )

    return {
        "before_proxy": before_proxy,
        "after_proxy": after_proxy,
        "action": action,
        "baseline_proxy": baseline_proxy,
    }
