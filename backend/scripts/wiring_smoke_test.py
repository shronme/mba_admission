import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wiring_smoke_test")


def http_request_json(method: str, url: str, body: dict | None = None) -> dict:
    data: bytes | None = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if hasattr(e, "read") else ""
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"http_error": {"code": e.code, "body": raw}}
        return {"http_error": {"code": e.code}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    enqueue_url = f"{args.base_url}/wiring/smoke"
    logger.info("POST %s (run wiring smoke)", enqueue_url)

    enqueue_payload = http_request_json("POST", enqueue_url, body={})

    if not isinstance(enqueue_payload, dict):
        logger.error("Unexpected response: %r", enqueue_payload)
        return 3

    ok_db = bool(enqueue_payload.get("db_connected"))
    if ok_db:
        logger.info("Wiring smoke succeeded.")
        print(json.dumps(enqueue_payload, indent=2))
        return 0

    logger.error("Wiring smoke failed.")
    print(json.dumps(enqueue_payload, indent=2))
    return 6


if __name__ == "__main__":
    raise SystemExit(main())

