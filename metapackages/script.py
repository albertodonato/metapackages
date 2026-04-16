from pathlib import Path
import shutil

import click
import yaml

from .distribution import get_distribution
from .gpg import GPG
from .packages import Package, PackageDefinition, write_packages
from .utils import msg, tempdir

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
def packages() -> None:
    """List packages for the current distribution as YAML"""
    distro = get_distribution()
    result: dict[str, dict] = {}
    for path in (PACKAGES_DIR / "defs").glob("*.yaml"):
        definition = PackageDefinition.model_validate(
            yaml.safe_load(path.read_text())
        )
        package = Package.from_definition(definition, distro.name)
        if package:
            result[package.name] = package.model_dump(exclude={"name"})
    click.echo(yaml.dump(result, default_flow_style=False), nl=False)


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

    # add static files
    for path in STATIC_DIR.iterdir():
        msg("CPY", path, REPO_DIR)
        shutil.copy(path, REPO_DIR)
