import os
from pathlib import Path

from .utils import run


class GPG:
    """Wrapper for the gpg command."""

    def __init__(self, work_dir: Path, secret_key: Path) -> None:
        self.gpg_dir = work_dir / "gnupghome"
        self.secret_key = secret_key

    def setup(self) -> None:
        self.gpg_dir.mkdir()
        with self.secret_key.open("rb") as seckey:
            run(
                ("gpg", "--import"),
                stdin=seckey,
                env={
                    "PATH": os.environ["PATH"],
                    "GNUPGHOME": str(self.gpg_dir),
                },
            )
