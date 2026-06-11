"""Container health probe — exits 0 when core components are healthy."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    try:
        from app.bootstrap import build_application

        app = build_application()
        components = app.health_service.check_all()
        app.worker.stop()

        unhealthy = [c for c in components if c.status == "unhealthy"]
        if unhealthy:
            names = ", ".join(c.name for c in unhealthy)
            print(f"UNHEALTHY: {names}", file=sys.stderr)
            return 1

        print("HEALTHY")
        return 0
    except Exception as exc:
        print(f"HEALTHCHECK FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())