from collections.abc import Iterator
from pathlib import Path
from string import Template
from typing import Self

from pydantic import BaseModel, Field
import yaml

from .distribution import Distribution
from .utils import msg

Dependencies = list[str | dict[str, str]]


class PackageDefinition(BaseModel):
    name: str
    version: int
    maintainer: str
    title: str
    description: str
    url: str
    dependencies: Dependencies
    distributions: list[str] = Field(default_factory=list)


class Package(BaseModel):
    name: str
    version: int
    maintainer: str
    title: str
    description: str
    url: str
    dependencies: str

    @classmethod
    def from_definition(
        cls,
        definition: PackageDefinition,
        distro: Distribution,
    ) -> Self | None:
        if (
            definition.distributions
            and distro.name not in definition.distributions
        ):
            return None

        deps = cls._distro_dependencies(definition.dependencies, distro)
        if not deps:
            return None

        details = definition.model_dump(exclude={"dependencies"})
        details["dependencies"] = deps
        return cls.model_validate(details)

    @classmethod
    def _distro_dependencies(
        cls,
        dependencies: Dependencies,
        distro: Distribution,
    ) -> str:
        deps: set[str] = set()
        for dep in dependencies:
            if isinstance(dep, str):
                deps.add(dep)
            else:
                if entry := dep.get(distro.name):
                    deps.add(entry)

        return distro.dependencies_expr(sorted(deps))


def write_packages(
    work_dir: Path, packages_dir: Path, distro: Distribution
) -> Iterator[Path]:
    defs_dir = work_dir / "packages"
    defs_dir.mkdir()

    template = Template(
        (packages_dir / "templates" / f"{distro.name}.template").read_text()
    )
    for package_def in (packages_dir / "defs").glob("*.yaml"):
        path = defs_dir / package_def.stem

        content = yaml.safe_load(package_def.read_text())
        definition = PackageDefinition.model_validate(content)
        package = Package.from_definition(definition, distro)
        if not package:
            msg("PKG[SKIP]", str(path))
            continue

        msg("PKG", str(path))
        path.write_text(template.substitute(package.model_dump()))
        yield path
