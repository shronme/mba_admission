import os
import time


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    db_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/admissions")
    print(f"worker booted with REDIS_URL={redis_url} DATABASE_URL={db_url}")
    while True:
        time.sleep(30)
        print("worker heartbeat")


if __name__ == "__main__":
    main()
