from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
COMPOSE_FILE = ROOT / "infra" / "docker-compose.yml"
REQUIRED_COMMANDS = ("docker", "uv", "npm")
DEFAULT_PORTS = (("API", 8000), ("Web", 3000))


def resolve_command(command: Sequence[str]) -> list[str]:
    executable = shutil.which(command[0])
    if executable is None:
        return list(command)
    if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", executable, *command[1:]]
    return [executable, *command[1:]]


def command_env(command: Sequence[str], env: dict[str, str] | None = None) -> dict[str, str] | None:
    if command[0] != "uv":
        return env
    merged = os.environ.copy()
    if env is not None:
        merged.update(env)
    uv_cache_dir = ROOT / ".local" / "uv-cache"
    uv_cache_dir.mkdir(parents=True, exist_ok=True)
    merged.setdefault("UV_CACHE_DIR", str(uv_cache_dir))
    return merged


def run(
    command: Sequence[str],
    cwd: Path = ROOT,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    print(f"> {' '.join(command)}")
    return subprocess.run(resolve_command(command), cwd=cwd, check=check, env=command_env(command, env))


def run_stdout_to_file(command: Sequence[str], output_path: Path) -> None:
    print(f"> {' '.join(command)} > {output_path}")
    with output_path.open("wb") as output_file:
        subprocess.run(resolve_command(command), cwd=ROOT, check=True, stdout=output_file)


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"Missing required command: {command}")


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def start_infra() -> None:
    require_command("docker")
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "postgres", "redis", "minio"])


def prepare_api(skip_install: bool) -> None:
    require_command("uv")
    if not skip_install:
        run(["uv", "sync"], cwd=API_DIR)
    run(["uv", "run", "alembic", "upgrade", "head"], cwd=API_DIR)


def local_runtime_env(args: argparse.Namespace) -> dict[str, str]:
    local_root = ROOT / ".local"
    database_path = local_root / "study_agent.db"
    storage_root = local_root / "storage"
    env = os.environ.copy()
    env.update(
        {
            "RUNTIME_PROFILE": "local",
            "API_PUBLIC_URL": f"http://{args.host}:{args.api_port}",
            "DATABASE_URL": f"sqlite+aiosqlite:///{database_path.as_posix()}",
            "STORAGE_BACKEND": "filesystem",
            "LOCAL_STORAGE_ROOT": str(storage_root),
            "LOCAL_SETTINGS_PATH": str(local_root / "settings.json"),
        }
    )
    return env


def prepare_api_local(skip_install: bool, env: dict[str, str]) -> None:
    require_command("uv")
    (ROOT / ".local" / "storage" / "sources").mkdir(parents=True, exist_ok=True)
    if not skip_install:
        run(["uv", "sync"], cwd=API_DIR, env=env)
    run(["uv", "run", "python", "-m", "scripts.prepare_local"], cwd=API_DIR, env=env)


def prepare_web(skip_install: bool) -> None:
    require_command("npm")
    if skip_install:
        return
    if not (WEB_DIR / "node_modules").exists():
        run(["npm", "install"], cwd=WEB_DIR)


def spawn(command: Sequence[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    print(f"> {' '.join(command)}")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(
        resolve_command(command),
        cwd=cwd,
        env=command_env(command, env),
        creationflags=creationflags,
    )


def stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    process.send_signal(signal.SIGTERM)


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
            stop_process_tree(process)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        return 0


def local(args: argparse.Namespace) -> int:
    env = local_runtime_env(args)
    if not args.web_only:
        prepare_api_local(skip_install=args.skip_install, env=env)
    if not args.api_only:
        prepare_web(skip_install=args.skip_install)

    processes: list[subprocess.Popen] = []
    if not args.web_only:
        processes.append(
            spawn(
                ["uv", "run", "uvicorn", "app.main:app", "--reload", "--host", args.host, "--port", str(args.api_port)],
                cwd=API_DIR,
                env=env,
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
    print("Profile: local (SQLite + filesystem storage)")
    print(f"API: http://{args.host}:{args.api_port}")
    print(f"Web: http://{args.host}:{args.web_port}")
    print("Press Ctrl+C to stop.")
    return wait_for_processes(processes)


def docker_dev(args: argparse.Namespace) -> int:
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
    errors: list[str] = []
    for command in ("uv", "npm"):
        if shutil.which(command) is None:
            errors.append(f"Missing required command: {command}")

    for label, port in DEFAULT_PORTS:
        if not is_port_available("127.0.0.1", port):
            errors.append(f"{label} port check failed: Port {port} is already in use.")

    if errors:
        print("Local environment check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Local profile check passed.")
    print(f"SQLite: {(ROOT / '.local' / 'study_agent.db')}")
    print(f"Storage: {(ROOT / '.local' / 'storage')}")
    return 0


def docker_check(_: argparse.Namespace) -> int:
    errors: list[str] = []
    for command in REQUIRED_COMMANDS:
        if shutil.which(command) is None:
            errors.append(f"Missing required command: {command}")
    if errors:
        print("Docker environment check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "config"])
    print("Docker compose config is valid.")
    return 0


def docker(args: argparse.Namespace) -> int:
    require_command("docker")
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
    if args.build:
        command.append("--build")
    run(command)
    return 0


def reset_db(args: argparse.Namespace) -> int:
    commands = [
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "postgres", "redis", "minio"],
    ]
    if not args.yes:
        print("reset-db dry run. This would run:")
        for command in commands:
            print(f"- {' '.join(command)}")
        print("Re-run with --yes to execute. No data was changed.")
        return 0

    require_command("docker")
    for command in commands:
        run(command)
    prepare_api(skip_install=True)
    return 0


def seed_demo(_: argparse.Namespace) -> int:
    seed_script = API_DIR / "scripts" / "seed_dev.py"
    if not seed_script.exists():
        print("No stable demo seed script found. Expected apps/api/scripts/seed_dev.py.")
        return 1
    if shutil.which("uv") is None:
        print("Missing required command: uv")
        return 1
    run(["uv", "run", "python", "-m", "scripts.seed_dev"], cwd=API_DIR)
    return 0


def backup(args: argparse.Namespace) -> int:
    output_dir = Path(args.output) if args.output else ROOT / ".local" / "backups" / datetime.now().strftime("local-%Y%m%d-%H%M%S")
    commands = [
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "study_agent",
            "study_agent",
        ],
        ["docker", "compose", "-f", str(COMPOSE_FILE), "cp", "minio:/data", str(output_dir / "minio-data")],
    ]
    if args.dry_run:
        print("backup dry run. This would create:")
        print(f"- {output_dir}")
        for command in commands:
            print(f"- {' '.join(command)}")
        if args.include_env:
            print("- copy .env into the backup directory")
        print("Re-run without --dry-run to execute. No data was changed.")
        return 0

    require_command("docker")
    output_dir.mkdir(parents=True, exist_ok=True)

    postgres_dump = output_dir / "postgres.sql"
    run_stdout_to_file(commands[0], postgres_dump)
    run(commands[1])
    env_included = False
    env_path = ROOT / ".env"
    if args.include_env and env_path.exists():
        shutil.copy2(env_path, output_dir / ".env")
        env_included = True
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "postgres_dump": "postgres.sql",
        "minio_data": "minio-data",
        "env_included": env_included,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Backup written to {output_dir}")
    return 0


def restore(args: argparse.Namespace) -> int:
    backup_dir = Path(args.backup_dir)
    postgres_dump = backup_dir / "postgres.sql"
    minio_data = backup_dir / "minio-data"
    if not postgres_dump.exists():
        print(f"Missing backup file: {postgres_dump}")
        return 1
    if not minio_data.exists():
        print(f"Missing backup directory: {minio_data}")
        return 1
    commands = [
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "postgres", "minio"],
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "study_agent",
            "-d",
            "study_agent",
            "-c",
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
        ],
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "minio", "sh", "-c", "rm -rf /data/*"],
        ["docker", "compose", "-f", str(COMPOSE_FILE), "cp", str(minio_data), "minio:/data"],
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "study_agent",
            "-d",
            "study_agent",
            "-f",
            "-",
        ],
    ]
    if not args.yes:
        print("restore dry run. This would restore Postgres and MinIO from:")
        print(f"- {backup_dir}")
        print("Re-run with --yes to execute. No data was changed.")
        return 0

    require_command("docker")
    run(commands[0])
    run(commands[1])
    run(commands[2])
    run(commands[3])
    print(f"> {' '.join(commands[4])} < {postgres_dump}")
    with postgres_dump.open("rb") as input_file:
        subprocess.run(resolve_command(commands[4]), cwd=ROOT, check=True, stdin=input_file)
    prepare_api(skip_install=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local study_agent developer launcher.")
    subcommands = parser.add_subparsers(dest="command")

    local_parser = subcommands.add_parser("local", help="Start API and web with SQLite and filesystem storage.")
    local_parser.add_argument("--host", default="127.0.0.1")
    local_parser.add_argument("--api-port", type=int, default=8000)
    local_parser.add_argument("--web-port", type=int, default=3000)
    local_parser.add_argument("--skip-install", action="store_true")
    local_parser.add_argument("--api-only", action="store_true")
    local_parser.add_argument("--web-only", action="store_true")
    local_parser.set_defaults(func=local)

    dev_parser = subcommands.add_parser("dev", help="Alias for local mode.")
    dev_parser.add_argument("--host", default="127.0.0.1")
    dev_parser.add_argument("--api-port", type=int, default=8000)
    dev_parser.add_argument("--web-port", type=int, default=3000)
    dev_parser.add_argument("--skip-install", action="store_true")
    dev_parser.add_argument("--api-only", action="store_true")
    dev_parser.add_argument("--web-only", action="store_true")
    dev_parser.set_defaults(func=local)

    docker_dev_parser = subcommands.add_parser("docker-dev", help="Start Docker infra, then host API and web app.")
    docker_dev_parser.add_argument("--host", default="127.0.0.1")
    docker_dev_parser.add_argument("--api-port", type=int, default=8000)
    docker_dev_parser.add_argument("--web-port", type=int, default=3000)
    docker_dev_parser.add_argument("--skip-install", action="store_true")
    docker_dev_parser.add_argument("--skip-infra", action="store_true")
    docker_dev_parser.add_argument("--api-only", action="store_true")
    docker_dev_parser.add_argument("--web-only", action="store_true")
    docker_dev_parser.set_defaults(func=docker_dev)

    docker_parser = subcommands.add_parser("docker", help="Start Docker Compose deployment stack.")
    docker_parser.add_argument("--build", action="store_true", help="Build API/Web images before starting.")
    docker_parser.set_defaults(func=docker)

    check_parser = subcommands.add_parser("check", help="Run local environment checks.")
    check_parser.set_defaults(func=check)

    docker_check_parser = subcommands.add_parser("docker-check", help="Run Docker profile checks.")
    docker_check_parser.set_defaults(func=docker_check)

    reset_parser = subcommands.add_parser("reset-db", help="Show or run local database reset steps.")
    reset_parser.add_argument("--yes", action="store_true", help="Run docker compose down/up.")
    reset_parser.set_defaults(func=reset_db)

    seed_parser = subcommands.add_parser("seed-demo", help="Seed local demo data when a stable script exists.")
    seed_parser.set_defaults(func=seed_demo)

    backup_parser = subcommands.add_parser("backup", help="Back up local Postgres and MinIO data.")
    backup_parser.add_argument("--output", help="Backup output directory. Defaults to .local/backups/local-<timestamp>.")
    backup_parser.add_argument("--dry-run", action="store_true", help="Show backup actions without writing files.")
    backup_parser.add_argument("--include-env", action="store_true", help="Include .env in the backup directory.")
    backup_parser.set_defaults(func=backup)

    restore_parser = subcommands.add_parser("restore", help="Show or run local restore from a backup directory.")
    restore_parser.add_argument("backup_dir")
    restore_parser.add_argument("--yes", action="store_true", help="Restore Postgres and MinIO from the backup.")
    restore_parser.set_defaults(func=restore)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw_args = list(argv or [])
    if not raw_args or (raw_args[0].startswith("-") and raw_args[0] not in {"-h", "--help"}):
        raw_args = ["dev", *raw_args]
    args = parser.parse_args(raw_args)
    if getattr(args, "api_only", False) and getattr(args, "web_only", False):
        parser.error("--api-only and --web-only cannot be used together")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
