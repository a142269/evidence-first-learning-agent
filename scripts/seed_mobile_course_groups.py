"""Idempotently seed the mobile course group and demo direct conversations."""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import init_db  # noqa: E402
from backend.app.repositories.mobile_chat_repo import seed_mobile_course_groups  # noqa: E402


def main() -> None:
    init_db()
    print(json.dumps(seed_mobile_course_groups(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
