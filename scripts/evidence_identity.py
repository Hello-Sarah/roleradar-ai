"""Privacy-safe capture identities and replay checks for new release evidence."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from functools import lru_cache
from pathlib import Path
from zipfile import BadZipFile, ZipFile

SCREENSHOT_LEDGER = "browser-results/screenshot-captures.json"
SCREENSHOT_STATES = {
    "dashboard": ("dashboard", "page"),
    "job-detail": ("jobs", "page"),
    "watch-list": ("watchlist", "page"),
    "cv-library": ("cv_library", "page"),
    "copilot-confirmation": ("analyze", "confirmation"),
    "error": ("dashboard", "error"),
    "copilot": ("jobs", "copilot"),
}
SYSTEM_HEADINGS = {
    "en": {
        "Good decisions, clearly prioritized.": "dashboard",
        "Jobs": "jobs",
        "Watch List": "watchlist",
        "CV Library": "cv_library",
        "Analyze Job": "analyze",
    },
    "zh-Hans": {
        "把重要的职业决策排在前面。": "dashboard",
        "职位": "jobs",
        "关注列表": "watchlist",
        "CV 库": "cv_library",
        "分析职位": "analyze",
    },
}


def png_identity(path: Path) -> tuple[int, int, str]:
    """Decode browser PNG scanlines, CRCs and pixels; reject malformed/oversized images."""
    return _decode_png(path.read_bytes())


@lru_cache(maxsize=128)
def _decode_png(data: bytes) -> tuple[int, int, str]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not PNG")
    offset, compressed, dimensions, ended = 8, bytearray(), None, False
    while offset < len(data):
        size = struct.unpack("!I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + size]
        crc = data[offset + 8 + size : offset + 12 + size]
        if (
            len(chunk) != size
            or len(crc) != 4
            or zlib.crc32(kind + chunk) != struct.unpack("!I", crc)[0]
        ):
            raise ValueError("invalid PNG chunk")
        offset += size + 12
        if kind == b"IHDR":
            if dimensions is not None or len(chunk) != 13:
                raise ValueError("invalid IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                "!IIBBBBB", chunk
            )
            if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
                raise ValueError("unsupported browser PNG format")
            if not 0 < width <= 10000 or not 0 < height <= 30000 or width * height > 40_000_000:
                raise ValueError("oversized PNG")
            dimensions = width, height, (3 if color == 2 else 4)
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            ended = True
            break
    if not ended or offset != len(data) or dimensions is None:
        raise ValueError("incomplete PNG")
    width, height, channels = dimensions
    stride = width * channels
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), (stride + 1) * height + 1)
    if not decoder.eof or decoder.unused_data or len(raw) != (stride + 1) * height:
        raise ValueError("invalid PNG pixel stream")
    pixels, previous = bytearray(), bytearray(stride)
    for row_index in range(height):
        start = row_index * (stride + 1)
        filter_type = raw[start]
        row = bytearray(raw[start + 1 : start + 1 + stride])
        if filter_type > 4:
            raise ValueError("invalid PNG filter")
        if filter_type == 0:
            pixels.extend(row)
            previous = row
            continue
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            up, corner = previous[index], (previous[index - channels] if index >= channels else 0)
            if filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                estimate = left + up - corner
                distances = abs(estimate - left), abs(estimate - up), abs(estimate - corner)
                predictor = (left, up, corner)[distances.index(min(distances))]
            else:
                predictor = 0
            row[index] = (row[index] + predictor) % 256
        pixels.extend(row)
        previous = row
    return width, height, hashlib.sha256(struct.pack("!II", width, height) + pixels).hexdigest()


def trace_identity(path: Path, browser: str, test_name: str, interval: tuple[float, float]) -> str:
    """Require an exact context, successful completed workflow and usable replay assets."""
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or archive.testzip() is not None:
                raise ValueError("bad trace archive")
            if sum(entry.file_size for entry in archive.infolist()) > 100_000_000:
                raise ValueError("oversized trace archive")
            streams = [name for name in names if name.endswith(".trace")]
            networks = [name for name in names if name.endswith(".network")]
            if len(streams) != 1 or len(networks) != 1:
                raise ValueError("missing/ambiguous replay streams")
            events = [
                json.loads(line) for line in archive.read(streams[0]).decode().splitlines() if line
            ]
            network = [
                json.loads(line) for line in archive.read(networks[0]).decode().splitlines() if line
            ]
            contexts = [event for event in events if event.get("type") == "context-options"]
            file = (
                "test_copilot_confirmation.py"
                if "confirmation_before_write" in test_name
                else "test_primary_loop.py"
            )
            viewport = (
                {"width": 390, "height": 844}
                if "390px" in test_name
                else {"width": 1440, "height": 1100}
            )
            if len(contexts) != 1:
                raise ValueError("ambiguous context")
            context = contexts[0]
            if (
                context.get("browserName") != browser
                or context.get("title") != f"tests/e2e/{file}::{test_name}[{browser}]"
                or context.get("options", {}).get("viewport") != viewport
                or context.get("options", {}).get("locale") != "en-US"
                or not interval[0] <= context.get("wallTime", 0) / 1000 <= interval[1]
            ):
                raise ValueError("wrong trace context")
            before = [event for event in events if event.get("type") == "before"]
            after = [event for event in events if event.get("type") == "after"]
            ids = [event.get("callId") for event in before]
            completions = [event.get("callId") for event in after]
            if (
                not ids
                or any(not isinstance(item, str) or not item for item in ids + completions)
                or len(set(ids)) != len(ids)
                or len(set(completions)) != len(completions)
                or set(ids) != set(completions)
                or any(event.get("error") for event in after)
            ):
                raise ValueError("failed or incomplete actions")
            complete = {event["callId"]: event for event in after}
            if any(
                complete[event["callId"]].get("endTime", -1) < event.get("startTime", 0)
                for event in before
            ):
                raise ValueError("invalid action time")
            snapshots = [
                event["snapshot"] for event in events if event.get("type") == "frame-snapshot"
            ]
            if not any(
                isinstance(snapshot.get("html"), list)
                and snapshot.get("pageId")
                and snapshot.get("frameId")
                for snapshot in snapshots
            ):
                raise ValueError("missing DOM replay snapshot")
            resources = [
                event.get("snapshot", {}).get("response", {}).get("content", {}).get("_file")
                for event in network
            ]
            resources = [resource for resource in resources if resource]
            if not resources or any(
                resource not in names or not archive.read(resource) for resource in resources
            ):
                raise ValueError("missing replay resource")
            for event in events:
                if (
                    event.get("type") == "screencast-frame"
                    and event.get("file", event.get("sha1")) not in names
                ):
                    raise ValueError("missing screencast resource")
            checkpoints = [
                ("click", "Extract fields"),
                ("click", "Confirm & analyze"),
                ("expect", "Analysis complete"),
            ]
            if "confirmation_before_write" in test_name:
                checkpoints += [
                    ("fill", "Change status to Applied"),
                    ("expect", "Review this proposed action"),
                    ("focus", "Confirm action"),
                    ("keyboardPress", "Enter"),
                    ("expect", "Updated the application status"),
                ]
            else:
                checkpoints += [
                    ("keyboardType", "Saved"),
                    ("expect", '"string": "Saved"'),
                    ("keyboardType", "Applied"),
                    ("expect", '"string": "Applied"'),
                ]
                if "390px" in test_name:
                    checkpoints += [
                        ("click", "Open Career Copilot"),
                        ("expect", "internal:role=dialog"),
                        ("evaluateExpression", "scrollWidth <= window.innerWidth"),
                        ("boundingBox", ""),
                    ]
                else:
                    checkpoints += [
                        ("fill", "Synthetic application event for acceptance testing"),
                        ("expect", "Synthetic application event for acceptance testing"),
                        ("click", "Add Watch List company"),
                        ("fill", "Synthetic Watch Labs"),
                        ("expect", "Synthetic Watch Labs"),
                        ("click", "Scan CV folder"),
                        ("expect", "synthetic-redacted-cv.txt"),
                        ("click", "Generate tailored CV"),
                        ("expect", "Generated CV #"),
                    ]
            position = 0
            for method, marker in checkpoints:
                found = next(
                    (
                        index
                        for index in range(position, len(before))
                        if before[index].get("method") == method
                        and marker in json.dumps(before[index].get("params", {}))
                    ),
                    None,
                )
                if found is None:
                    raise ValueError("missing successful workflow checkpoint")
                position = found + 1
            content = archive.read(streams[0]) + archive.read(networks[0])
            return hashlib.sha256(content).hexdigest()
    except (
        OSError,
        BadZipFile,
        UnicodeDecodeError,
        json.JSONDecodeError,
        AttributeError,
        TypeError,
        KeyError,
    ) as error:
        raise ValueError("invalid trace") from error
