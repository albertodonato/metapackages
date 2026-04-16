from abc import ABC, abstractmethod
import os
from pathlib import Path
import shutil

from .utils import run


class Repo(ABC):
    distribution: str

    def __init__(
        self,
        work_dir: Path,
        repo_base_dir: Path,
        config_base_dir: Path,
        gpg_dir: Path,
    ) -> None:
        self.work_dir = work_dir
        self.repo_dir = repo_base_dir / self.distribution
        self.config_dir = config_base_dir / self.distribution
        self.gpg_dir = gpg_dir
        self.post_init()

    def setup(self) -> None:
        shutil.rmtree(self.repo_dir, ignore_errors=True)
        self.repo_dir.mkdir()
        self.post_setup()

    def post_init(self) -> None: ...

    def post_setup(self) -> None: ...

    @abstractmethod
    def build_and_import(self, *packages: Path) -> None: ...


class DebRepo(Repo):
    distribution = "ubuntu"

    _repo_suite = "unstable"

    def post_init(self) -> None:
        self.base_dir = self.work_dir / "reprepro"
        self.packages_dir = self.work_dir / "equivs"

    def post_setup(self) -> None:
        self.base_dir.mkdir()
        self.packages_dir.mkdir()

    def build_and_import(self, *packages: Path) -> None:
        for package in packages:
            run(("equivs-build", "-f", str(package)), cwd=self.packages_dir)
            for command, suffix in (
                ("include", "changes"),
                ("includedsc", "dsc"),
            ):
                for path in self.packages_dir.glob(
                    f"{package.name}*.{suffix}"
                ):
                    self._reprepro(
                        "--outdir",
                        str(self.repo_dir),
                        "-VVV",
                        command,
                        self._repo_suite,
                        str(path),
                    )

    def _reprepro(self, *args: str) -> None:
        run(
            ("reprepro", *args),
            env={
                "PATH": os.environ["PATH"],
                "REPREPRO_CONFIG_DIR": str(self.config_dir / "reprepro"),
                "REPREPRO_BASE_DIR": str(self.base_dir),
                "GNUPGHOME": str(self.gpg_dir),
            },
        )


class ArchRepo(Repo):
    distribution = "arch"

    REPO_NAME = "personal"

    def post_init(self) -> None:
        self.base_dir = self.work_dir / "makepkg"

    def post_setup(self) -> None:
        self.base_dir.mkdir()

    def build_and_import(self, *packages: Path) -> None:
        for package in packages:
            pkgbuild = self.base_dir / "PKGBUILD"
            shutil.copy(package, pkgbuild)
            self._makepkg(self.base_dir)
            pkgbuild.unlink()
            for path in self.base_dir.glob("*.zst"):
                shutil.copy(path, self.repo_dir)
                self._repo_add()

    def _makepkg(self, path: Path) -> None:
        run(
            ("makepkg",),
            cwd=path,
        )

    def _repo_add(self) -> None:
        packages = (str(path) for path in self.repo_dir.glob("*.zst"))
        run(
            ("repo-add", "--sign", f"{self.REPO_NAME}.db.tar.gz", *packages),
            env={"GNUPGHOME": str(self.gpg_dir)},
            cwd=self.repo_dir,
        )
