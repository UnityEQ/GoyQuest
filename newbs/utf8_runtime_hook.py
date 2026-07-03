"""PyInstaller runtime hook: UTF-8 stdio before any app code runs (Windows cp1252 fix)."""

import io
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream is None:
        continue
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
        continue
    except (AttributeError, OSError, ValueError):
        pass
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        continue
    try:
        setattr(
            sys,
            stream_name,
            io.TextIOWrapper(
                buffer,
                encoding="utf-8",
                errors="replace",
                line_buffering=stream.line_buffering,
            ),
        )
    except (AttributeError, OSError, ValueError):
        pass