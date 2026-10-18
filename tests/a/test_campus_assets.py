import re
from pathlib import Path


def test_embedded_map_references_existing_shared_campus_assets():
    public = Path(__file__).resolve().parents[2] / "frontend/public"
    assets = public / "integrated-map/assets"
    references = []
    for file in assets.iterdir():
        if file.suffix in {".css", ".js"}:
            text = file.read_text(encoding="utf-8")
            assert "/integrated-map/pixel-campus/" not in text
            references.extend(re.findall(r"/pixel-campus/[\w./-]+\.png", text))
    assert references
    assert all((public / path.lstrip("/")).is_file() for path in references)
