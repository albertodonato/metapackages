from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
import subprocess
from tempfile import mkdtemp
from typing import IO, Any

import click


def msg(prefix: str, *message: Any) -> None:
    """Print a message to stderr."""
    click.echo(f"--> {prefix}: {' '.join(str(m) for m in message)}", err=True)


def run(
    cmd: tuple[str, ...],
    stdin: IO[bytes] | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> str:
    """Execute a process and return its stdout."""
    msg("RUN", *cmd)
    process = subprocess.run(
        cmd,
        stdin=stdin,
        capture_output=True,
        env=env,
        cwd=cwd,
    )
    if process.returncode != 0:
        print("stdout:")
        for line in process.stdout.decode().splitlines():
            print(f"| {line}")
        print("stderr:")
        for line in process.stderr.decode().splitlines():
            print(f"| {line}")
        raise click.ClickException(f"Command failed: {' '.join(cmd)}")
    return process.stdout.decode()


@contextmanager
def tempdir(cleanup: bool = True) -> Iterator[Path]:
    """Contextmanager with temporary directory."""
    path = Path(mkdtemp())
    try:
        yield path
    except Exception:
        if cleanup:
            rmtree(path)
        raise
