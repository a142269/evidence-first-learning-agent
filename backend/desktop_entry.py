from __future__ import annotations

import argparse
import os

import uvicorn

from backend.app.main import app as fastapi_app


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 desktop backend entry")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=int(os.getenv("PORT", "18000")), type=int)
    args = parser.parse_args()

    os.environ.setdefault("A3_OFFLINE_DEMO", "1")
    os.environ.setdefault("PORT", str(args.port))

    uvicorn.run(
        fastapi_app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
