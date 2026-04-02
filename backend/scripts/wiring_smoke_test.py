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
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    args = parser.parse_args()

    enqueue_url = f"{args.base_url}/wiring/smoke"
    start = time.time()
    logger.info("POST %s (enqueue smoke job)", enqueue_url)

    enqueue_payload = http_request_json("POST", enqueue_url, body={})

    job_id = enqueue_payload.get("job_id")
    if not job_id:
        logger.error("Unexpected enqueue response: %s", enqueue_payload)
        return 3

    logger.info("Enqueued job_id=%s; polling every %.1fs (timeout %ds)", job_id, args.poll_interval_seconds, args.timeout_seconds)

    status_url = f"{args.base_url}/wiring/smoke/{job_id}"
    last_state = None
    poll_n = 0

    while True:
        elapsed = time.time() - start
        if elapsed > args.timeout_seconds:
            logger.error("Timed out after %.1fs waiting for job to complete", elapsed)
            return 4

        status_payload = http_request_json("GET", status_url)
        poll_n += 1

        state = status_payload.get("state")
        if state != last_state:
            logger.info("State: %s (elapsed %.1fs, poll #%d)", state, elapsed, poll_n)
            last_state = state
        elif poll_n % 10 == 0:
            logger.info("Still waiting: state=%s elapsed=%.1fs", state, elapsed)

        if state == "SUCCESS":
            logger.info("Job finished successfully.")
            print(json.dumps(status_payload.get("result"), indent=2))
            return 0

        if state in {"FAILURE", "REVOKED"}:
            logger.error("Job ended in state=%s", state)
            print(json.dumps(status_payload.get("error") or status_payload, indent=2))
            return 6

        time.sleep(args.poll_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

