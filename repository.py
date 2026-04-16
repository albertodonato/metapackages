"""Build metapackages and a repository for them."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from string import Template
import subprocess
from tempfile import mkdtemp
import typing as t
from typing import Self

import click
import yaml

__version__ = "0.0.1"

BASE_DIR = Path.cwd()
STATIC_DIR = BASE_DIR / "static"
CONFS_DIR = BASE_DIR / "configs"
PACKAGES_DIR = BASE_DIR / "packages"
REPO_DIR = BASE_DIR / "repo"


@click.group()
def main() -> None:
    """Build distribution metapackages and a repository for them."""


@main.command()
def deps() -> None:
    """Print out dependencies for the target distribution"""
    distro = get_distro()
    packages = Repo.for_distro(distro).required_packages

    for dep in sorted(packages):
        print(dep)


@main.command()
@click.option(
    "--keep-workdir",
    is_flag=True,
    default=False,
    help="Keep working directory",
)
def build(keep_workdir: bool) -> None:
    """Build repository"""
    distro = get_distro()

    REPO_DIR.mkdir(exist_ok=True)

    with tempdir(cleanup=not keep_workdir) as work_dir:
        gpg = GPG(work_dir=work_dir, secret_key=Path("repo.key"))
        repo = Repo.for_distro(distro)(
            work_dir=work_dir,
            repo_base_dir=REPO_DIR,
            config_base_dir=CONFS_DIR,
            gpg_dir=gpg.gpg_dir,
        )

        msg("DIR", str(work_dir))

        if missing_packages := repo.missing_packages():
            raise click.ClickException(
                f"Missing required packages: {', '.join(sorted(missing_packages))}"
            )

        gpg.setup()
        repo.setup()
        packages = get_packages(work_dir, PACKAGES_DIR, distro)
        repo.build_and_import(*packages)

    _add_static_files(REPO_DIR)


def msg(prefix: str, *message: t.Any) -> None:
    click.echo(f"--> {prefix}: {' '.join(str(m) for m in message)}", err=True)


def get_distro() -> str:
    """Return the running distribution."""
    data = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
    )
    return data["ID"]


def run(
    cmd: tuple[str, ...],
    stdin: t.IO[bytes] | None = None,
    env: t.Mapping[str, str] | None = None,
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
def tempdir(cleanup: bool = True) -> t.Iterator[Path]:
    """Contextmanager with temporary directory."""
    path = Path(mkdtemp())
    try:
        yield path
    except Exception:
        if cleanup:
            shutil.rmtree(path)
        raise


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


class Repo(ABC):
    required_packages: frozenset[str] = frozenset()
    distribution: str

    _registry: t.ClassVar[dict[str, type[Self]]] = {}

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        Repo._registry[cls.distribution] = cls

    @classmethod
    def for_distro(cls, name: str) -> type[Self]:
        if name not in cls._registry:
            raise click.ClickException(f"Unsupported distribution: {name}")
        return cls._registry[name]

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

    def post_init(self) -> None: ...

    def missing_packages(self) -> frozenset[str]:
        return self.required_packages - self.installed_packages()

    @abstractmethod
    def setup(self) -> None: ...

    @abstractmethod
    def build_and_import(self, *packages: Path) -> None: ...

    @abstractmethod
    def installed_packages(self) -> set[str]: ...


class DebRepo(Repo):
    distribution = "ubuntu"

    required_packages = frozenset(
        (
            "equivs",
            "gpg",
            "reprepro",
        )
    )

    REPO_SUITE = "unstable"

    def post_init(self) -> None:
        self.base_dir = self.work_dir / "reprepro"
        self.packages_dir = self.work_dir / "equivs"

    def setup(self) -> None:
        shutil.rmtree(self.repo_dir, ignore_errors=True)
        self.repo_dir.mkdir()
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
                        self.REPO_SUITE,
                        str(path),
                    )

    def installed_packages(self) -> set[str]:
        return set(
            run(
                ("dpkg-query", "-W", "-f", "${Package} "),
            ).split()
        )

    def _reprepro(self, *args: str) -> None:
        run(
            ("reprepro", *args),
            env={
                "PATH": os.environ["PATH"],
                "REPREPRO_CONFIG_DIR": str(self.config_dir),
                "REPREPRO_BASE_DIR": str(self.base_dir),
                "GNUPGHOME": str(self.gpg_dir),
            },
        )


class ArchRepo(Repo):
    distribution = "arch"

    required_packages = frozenset(
        (
            "binutils",
            "fakeroot",
            "gnupg",
        )
    )

    REPO_NAME = "personal"

    def post_init(self) -> None:
        self.base_dir = self.work_dir / "makepkg"

    def setup(self) -> None:
        shutil.rmtree(self.repo_dir, ignore_errors=True)
        self.repo_dir.mkdir()
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

    def installed_packages(self) -> set[str]:
        return set(
            line.split(" ")[0] for line in run(("pacman", "-Q")).splitlines()
        )

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


def get_packages(
    work_dir: Path, packages_dir: Path, distro: str
) -> t.Iterator[Path]:
    defs_dir = work_dir / "packages"
    defs_dir.mkdir()

    template = Template(
        (packages_dir / "templates" / f"{distro}.template").read_text()
    )
    for package in (packages_dir / "defs").glob("*.yaml"):
        path = defs_dir / package.stem
        msg("PKG", str(path))
        context = _package_context(package, distro)
        path.write_text(template.substitute(context))
        yield path


def _package_context(source: Path, distro: str) -> dict[str, t.Any]:
    context: dict[str, t.Any] = yaml.safe_load(source.read_text())
    deps = []
    for dep in context.pop("dependencies"):
        if isinstance(dep, str):
            deps.append(dep)
        else:
            if entry := dep.get(distro):
                deps.append(entry)
    deps.sort()

    match distro:
        case "ubuntu":
            context["dependencies"] = ", ".join(deps)
        case "arch":
            context["dependencies"] = " ".join(deps)
    return context


def _add_static_files(target_dir: Path) -> None:
    for path in STATIC_DIR.iterdir():
        msg("CPY", path, target_dir)
        shutil.copy(path, target_dir)
