"""Small helpers for turning Agent-only text into real downloadable artifacts.

Chat resources must never advertise a download action unless a non-empty file is
registered behind it.  The multimodal generators already do this for PPT, audio,
video and code; quiz/evaluation Agents historically returned only Python dicts.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.api.v1.artifacts.registry import get_artifact_registry


ARTIFACT_ROOT = Path(__file__).resolve().parents[3] / "data" / "artifacts"


def register_markdown_artifact(
    *,
    artifact_type: str,
    title: str,
    content: str,
    session_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist Markdown, register it, and return the public download descriptor.

    An empty document is rejected so the UI cannot end up with a link that always
    returns 404.  IDs are deterministic for identical content, which also avoids
    duplicate files when a streamed message is retried.
    """
    body = str(content or "").strip()
    if not body:
        return {}

    kind = re.sub(r"[^0-9A-Za-z_-]", "", str(artifact_type or "document")) or "document"
    digest = hashlib.sha1(
        f"{kind}\0{session_id}\0{title}\0{body}".encode("utf-8")
    ).hexdigest()[:12]
    resource_id = f"{kind}_{digest}"

    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(title or kind)).strip(" ._")
    safe_title = safe_title[:64] or kind
    output_dir = ARTIFACT_ROOT / kind
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{safe_title}_{digest[:6]}.md"
    path.write_text(body + "\n", encoding="utf-8")

    record = get_artifact_registry().register(
        resource_id,
        kind,
        str(path),
        metadata={"title": title, **dict(metadata or {})},
        session_id=session_id,
    )
    ready = path.is_file() and path.stat().st_size > 0
    return {
        "id": resource_id,
        "type": record.type,
        "url": f"/api/v1/artifacts/download/{resource_id}",
        "filename": path.name,
        "exists": ready,
    }
