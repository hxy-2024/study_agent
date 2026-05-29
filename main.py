from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
COMPOSE_FILE = ROOT / "infra" / "docker-compose.yml"


def run(command: Sequence[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print(f"> {' '.join(command)}")
    return subprocess.run(command, cwd=cwd, check=check)


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"Missing required command: {command}")


def start_infra() -> None:
    require_command("docker")
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "postgres", "redis", "minio"])


def prepare_api(skip_install: bool) -> None:
    require_command("uv")
    if not skip_install:
        run(["uv", "sync"], cwd=API_DIR)
    run(["uv", "run", "alembic", "upgrade", "head"], cwd=API_DIR)


def prepare_web(skip_install: bool) -> None:
    require_command("npm")
    if skip_install:
        return
    if not (WEB_DIR / "node_modules").exists():
        run(["npm", "install"], cwd=WEB_DIR)


def spawn(command: Sequence[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    print(f"> {' '.join(command)}")
    return subprocess.Popen(command, cwd=cwd, env=env)


def wait_for_processes(processes: list[subprocess.Popen]) -> int:
    try:
        while True:
            for process in processes:
                if process.poll() is not None:
                    return int(process.returncode or 0)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping local dev processes...")
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        return 0


def dev(args: argparse.Namespace) -> int:
    if not args.skip_infra:
        start_infra()
    if not args.web_only:
        prepare_api(skip_install=args.skip_install)
    if not args.api_only:
        prepare_web(skip_install=args.skip_install)

    processes: list[subprocess.Popen] = []
    if not args.web_only:
        processes.append(
            spawn(
                ["uv", "run", "uvicorn", "app.main:app", "--reload", "--host", args.host, "--port", str(args.api_port)],
                cwd=API_DIR,
            )
        )
    if not args.api_only:
        processes.append(
            spawn(
                ["npm", "run", "dev", "--", "--host", args.host, "--port", str(args.web_port)],
                cwd=WEB_DIR,
            )
        )

    print("")
    print(f"API: http://{args.host}:{args.api_port}")
    print(f"Web: http://{args.host}:{args.web_port}")
    print("Press Ctrl+C to stop.")
    return wait_for_processes(processes)


def check(_: argparse.Namespace) -> int:
    require_command("docker")
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "config"])
    print("Docker compose config is valid.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local study_agent developer launcher.")
    subcommands = parser.add_subparsers(dest="command")

    dev_parser = subcommands.add_parser("dev", help="Start local infra, API, and web app.")
    dev_parser.add_argument("--host", default="127.0.0.1")
    dev_parser.add_argument("--api-port", type=int, default=8000)
    dev_parser.add_argument("--web-port", type=int, default=3000)
    dev_parser.add_argument("--skip-install", action="store_true")
    dev_parser.add_argument("--skip-infra", action="store_true")
    dev_parser.add_argument("--api-only", action="store_true")
    dev_parser.add_argument("--web-only", action="store_true")
    dev_parser.set_defaults(func=dev)

    check_parser = subcommands.add_parser("check", help="Run local environment checks.")
    check_parser.set_defaults(func=check)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args = parser.parse_args(["dev", *(argv or [])])
    if getattr(args, "api_only", False) and getattr(args, "web_only", False):
        parser.error("--api-only and --web-only cannot be used together")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
