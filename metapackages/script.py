from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import shutil
from string import Template
from tempfile import mkdtemp
from typing import Any

import click
import yaml

from .distribution import Distribution, get_distribution
from .gpg import GPG
from .utils import msg

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
    distro = get_distribution()
    for dep in sorted(distro.required_packages):
        click.echo(dep)


@main.command()
@click.option(
    "--keep-workdir",
    is_flag=True,
    default=False,
    help="Keep working directory",
)
def build(keep_workdir: bool) -> None:
    """Build repository"""
    distro = get_distribution()

    REPO_DIR.mkdir(exist_ok=True)

    with tempdir(cleanup=not keep_workdir) as work_dir:
        gpg = GPG(work_dir=work_dir, secret_key=Path("repo.key"))
        repo = distro.repository(
            work_dir=work_dir,
            repo_base_dir=REPO_DIR,
            config_base_dir=CONFS_DIR,
            gpg_dir=gpg.gpg_dir,
        )

        msg("DIR", str(work_dir))

        if missing_packages := distro.missing_packages():
            raise click.ClickException(
                f"Missing required packages: {', '.join(sorted(missing_packages))}"
            )

        gpg.setup()
        repo.setup()
        packages = write_packages(work_dir, PACKAGES_DIR, distro)
        repo.build_and_import(*packages)

    _add_static_files(REPO_DIR)


@contextmanager
def tempdir(cleanup: bool = True) -> Iterator[Path]:
    """Contextmanager with temporary directory."""
    path = Path(mkdtemp())
    try:
        yield path
    except Exception:
        if cleanup:
            shutil.rmtree(path)
        raise


def write_packages(
    work_dir: Path, packages_dir: Path, distro: Distribution
) -> Iterator[Path]:
    defs_dir = work_dir / "packages"
    defs_dir.mkdir()

    template = Template(
        (packages_dir / "templates" / f"{distro.name}.template").read_text()
    )
    for package in (packages_dir / "defs").glob("*.yaml"):
        path = defs_dir / package.stem
        msg("PKG", str(path))
        context = _package_context(package, distro)
        path.write_text(template.substitute(context))
        yield path


def _package_context(source: Path, distro: Distribution) -> dict[str, Any]:
    context: dict[str, Any] = yaml.safe_load(source.read_text())

    deps: set[str] = set()
    for dep in context.pop("dependencies"):
        if isinstance(dep, str):
            deps.add(dep)
        else:
            if entry := dep.get(distro.name):
                deps.add(entry)

    context["dependencies"] = distro.dependency_list(sorted(deps))
    return context


def _add_static_files(target_dir: Path) -> None:
    for path in STATIC_DIR.iterdir():
        msg("CPY", path, target_dir)
        shutil.copy(path, target_dir)
