from abc import ABC, abstractmethod
from typing import Any, ClassVar, Self
from pathlib import Path

from .repository import Repo, ArchRepo, DebRepo
from .utils import run

import click


class Distribution(ABC):
    name: str
    repository: type[Repo]
    required_packages: frozenset[str] = frozenset()

    _registry: ClassVar[dict[str, type[Self]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name"):
            Distribution._registry[cls.name] = cls

    @classmethod
    def instance(cls, name: str) -> Self:
        if name not in cls._registry:
            raise click.ClickException(f"Unsupported distribution: {name}")
        return cls._registry[name]()

    def missing_packages(self) -> frozenset[str]:
        return self.required_packages - self.installed_packages()

    @abstractmethod
    def installed_packages(self) -> set[str]: ...

    @abstractmethod
    def dependency_list(self, packages: list[str]) -> str: ...


def get_distribution() -> Distribution:
    """Return a Distribution instance for the current distro."""
    distro_data = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
    )
    return Distribution.instance(distro_data["ID"])


class DebDistribution(Distribution):
    name = "ubuntu"
    repository = DebRepo
    required_packages = frozenset(
        (
            "equivs",
            "gpg",
            "reprepro",
        )
    )

    def installed_packages(self) -> set[str]:
        return set(
            run(
                ("dpkg-query", "-W", "-f", "${Package} "),
            ).split()
        )

    def dependency_list(self, packages: list[str]) -> str:
        return ", ".join(packages)


class ArchDistribution(Distribution):
    name = "arch"
    repository = ArchRepo
    required_packages = frozenset(
        (
            "binutils",
            "fakeroot",
            "gnupg",
        )
    )

    def installed_packages(self) -> set[str]:
        return {
            line.split(" ")[0] for line in run(("pacman", "-Q")).splitlines()
        }

    def dependency_list(self, packages: list[str]) -> str:
        return " ".join(packages)


