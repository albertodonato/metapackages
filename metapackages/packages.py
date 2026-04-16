from collections.abc import Iterator
from pathlib import Path
from string import Template
from typing import Any

import yaml

from .distribution import Distribution
from .utils import msg


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
