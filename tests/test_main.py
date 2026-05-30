from __future__ import annotations

import contextlib
import io
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

import main


class MainCliTests(unittest.TestCase):
    def test_check_reports_missing_required_commands(self) -> None:
        calls: list[list[str]] = []

        with (
            mock.patch.object(main.shutil, "which", side_effect=lambda command: "docker" if command == "docker" else None),
            mock.patch.object(main, "run", side_effect=lambda command, **_: calls.append(list(command))),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main.main(["check"])

        self.assertEqual(result, 1)
        output = stdout.getvalue()
        self.assertIn("Missing required command: uv", output)
        self.assertIn("Missing required command: npm", output)
        self.assertEqual(calls, [])

    def test_check_reports_occupied_configured_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            occupied_port = listener.getsockname()[1]

            with (
                mock.patch.object(main, "DEFAULT_PORTS", (("API", occupied_port),), create=True),
                mock.patch.object(main.shutil, "which", return_value="tool"),
                mock.patch.object(main, "run", return_value=None),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main.main(["check"])

        self.assertEqual(result, 1)
        output = stdout.getvalue()
        self.assertIn(f"Port {occupied_port} is already in use", output)
        self.assertIn("API", output)

    def test_check_keeps_docker_compose_config_validation(self) -> None:
        calls: list[list[str]] = []

        with (
            mock.patch.object(main.shutil, "which", return_value="tool"),
            mock.patch.object(main, "run", side_effect=lambda command, **_: calls.append(list(command))),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main.main(["check"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [["docker", "compose", "-f", str(main.COMPOSE_FILE), "config"]])
        self.assertIn("Docker compose config is valid.", stdout.getvalue())

    def test_reset_db_without_yes_is_dry_run(self) -> None:
        calls: list[list[str]] = []

        with (
            mock.patch.object(main, "run", side_effect=lambda command, **_: calls.append(list(command))),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main.main(["reset-db"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        output = stdout.getvalue()
        self.assertIn("dry run", output.lower())
        self.assertIn("--yes", output)
        self.assertIn("docker compose", output)

    def test_seed_demo_runs_seed_dev_script_when_available(self) -> None:
        calls: list[tuple[list[str], main.Path]] = []

        with (
            mock.patch.object(main.shutil, "which", return_value="uv"),
            mock.patch.object(main, "run", side_effect=lambda command, cwd=main.ROOT, **_: calls.append((list(command), cwd))),
        ):
            result = main.main(["seed-demo"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [(["uv", "run", "python", "-m", "scripts.seed_dev"], main.API_DIR)])

    def test_seed_demo_reports_clear_error_when_script_missing(self) -> None:
        with (
            mock.patch.object(main, "API_DIR", main.ROOT / "missing-api"),
            mock.patch.object(main.shutil, "which", return_value="uv"),
            mock.patch.object(main, "run", return_value=subprocess.CompletedProcess(args=[], returncode=0)),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main.main(["seed-demo"])

        self.assertEqual(result, 1)
        self.assertIn("No stable demo seed script found", stdout.getvalue())

    def test_backup_writes_postgres_dump_and_copies_minio_data(self) -> None:
        calls: list[list[str]] = []
        dumps: list[tuple[list[str], main.Path]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = main.Path(temp_dir) / "backup"
            with (
                mock.patch.object(main.shutil, "which", return_value="docker"),
                mock.patch.object(main, "run", side_effect=lambda command, **_: calls.append(list(command))),
                mock.patch.object(
                    main,
                    "run_stdout_to_file",
                    side_effect=lambda command, output_path: dumps.append((list(command), output_path)),
                ),
            ):
                result = main.main(["backup", "--output", str(backup_dir)])
            manifest_exists = (backup_dir / "manifest.json").exists()

        self.assertEqual(result, 0)
        self.assertEqual(
            dumps,
            [
                (
                    [
                        "docker",
                        "compose",
                        "-f",
                        str(main.COMPOSE_FILE),
                        "exec",
                        "-T",
                        "postgres",
                        "pg_dump",
                        "-U",
                        "study_agent",
                        "study_agent",
                    ],
                    backup_dir / "postgres.sql",
                )
            ],
        )
        self.assertIn(["docker", "compose", "-f", str(main.COMPOSE_FILE), "cp", "minio:/data", str(backup_dir / "minio-data")], calls)
        self.assertTrue(manifest_exists)

    def test_restore_without_yes_is_dry_run(self) -> None:
        calls: list[list[str]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = main.Path(temp_dir)
            (backup_dir / "postgres.sql").write_text("-- dump", encoding="utf-8")
            (backup_dir / "minio-data").mkdir()
            with (
                mock.patch.object(main, "run", side_effect=lambda command, **_: calls.append(list(command))),
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                result = main.main(["restore", str(backup_dir)])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertIn("dry run", stdout.getvalue().lower())
        self.assertIn("--yes", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
