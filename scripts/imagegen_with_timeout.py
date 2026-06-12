#!/usr/bin/env python3
"""Run the system imagegen CLI with a longer OpenAI request timeout.

This wrapper keeps the bundled system engine unchanged. It imports the engine,
patches only its OpenAI client constructors, then delegates to engine.main().
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def timeout_seconds() -> float:
    raw = os.getenv("IMAGE_GEN_REQUEST_TIMEOUT", "600").strip()
    try:
        value = float(raw)
    except ValueError:
        fail(f"IMAGE_GEN_REQUEST_TIMEOUT must be a number, got {raw!r}")
    if value <= 0:
        fail("IMAGE_GEN_REQUEST_TIMEOUT must be greater than zero")
    return value


def load_engine(engine_path: Path):
    if not engine_path.exists():
        fail(f"system imagegen CLI not found: {engine_path}")
    spec = importlib.util.spec_from_file_location("_codex_system_imagegen", engine_path)
    if spec is None or spec.loader is None:
        fail(f"could not load system imagegen CLI: {engine_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_clients(engine) -> None:
    timeout = timeout_seconds()
    max_retries_raw = os.getenv("IMAGE_GEN_SDK_MAX_RETRIES", "2").strip()
    try:
        max_retries = int(max_retries_raw)
    except ValueError:
        fail(f"IMAGE_GEN_SDK_MAX_RETRIES must be an integer, got {max_retries_raw!r}")
    if max_retries < 0:
        fail("IMAGE_GEN_SDK_MAX_RETRIES must be >= 0")

    def create_client():
        try:
            from openai import OpenAI
        except ImportError:
            engine._die(f"openai SDK not installed in the active environment. {engine._dependency_hint('openai')}")
        return OpenAI(timeout=timeout, max_retries=max_retries)

    def create_async_client():
        try:
            from openai import AsyncOpenAI
        except ImportError:
            try:
                import openai as _openai  # noqa: F401
            except ImportError:
                engine._die(
                    f"openai SDK not installed in the active environment. {engine._dependency_hint('openai')}"
                )
            engine._die(
                "AsyncOpenAI not available in this openai SDK version. "
                f"{engine._dependency_hint('openai', upgrade=True)}"
            )
        return AsyncOpenAI(timeout=timeout, max_retries=max_retries)

    engine._create_client = create_client
    engine._create_async_client = create_async_client


def main() -> int:
    codex_home = Path(os.getenv("CODEX_HOME") or Path.home() / ".codex")
    engine_path = Path(os.getenv("IMAGE_GEN_ENGINE") or codex_home / "skills" / ".system" / "imagegen" / "scripts" / "image_gen.py")
    engine = load_engine(engine_path)
    patch_clients(engine)
    return int(engine.main())


if __name__ == "__main__":
    raise SystemExit(main())
