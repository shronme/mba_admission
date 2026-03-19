import argparse
import json
import sys
import time
import urllib.error
import urllib.request


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

    enqueue_payload = http_request_json("POST", enqueue_url, body={})

    job_id = enqueue_payload.get("job_id")
    if not job_id:
        print(f"Unexpected enqueue response: {enqueue_payload}", file=sys.stderr)
        return 3

    print(f"Enqueued wiring smoke job: {job_id}")

    status_url = f"{args.base_url}/wiring/smoke/{job_id}"
    last_state = None

    while True:
        if time.time() - start > args.timeout_seconds:
            print("Timed out waiting for job to complete.", file=sys.stderr)
            return 4

        status_payload = http_request_json("GET", status_url)

        state = status_payload.get("state")
        if state != last_state:
            print(f"State: {state}")
            last_state = state

        if state == "SUCCESS":
            print("Job result:")
            print(json.dumps(status_payload.get("result"), indent=2))
            return 0

        if state in {"FAILURE", "REVOKED"}:
            print("Job failed:")
            print(json.dumps(status_payload.get("error") or status_payload, indent=2))
            return 6

        time.sleep(args.poll_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

