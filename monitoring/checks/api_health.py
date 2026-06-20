import os
import httpx
from dotenv import load_dotenv

load_dotenv()

NAME = "api-health"


def check() -> dict:
    base_url = os.environ.get("PIPES_BASE_URL", "https://api.pipes.ai")
    try:
        r = httpx.get(f"{base_url}/health", timeout=10)
        if r.status_code == 200:
            return {"status": "ok", "detail": f"{base_url} → 200"}
        return {"status": "degraded", "detail": f"HTTP {r.status_code}"}
    except httpx.TimeoutException:
        return {"status": "down", "detail": "timed out after 10s"}
    except Exception as e:
        return {"status": "down", "detail": str(e)}


if __name__ == "__main__":
    import json
    print(json.dumps(check(), indent=2))
