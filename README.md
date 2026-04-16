# Repository with metapackages

This builds metapackages to automatically install all desired dependencies on a
Linux distribution.

Supported distributions:

- Arch Linux
- Ubuntu


## Build

Packages and repository are built via

```bash
uv run repository build
```

Result is in the `repo/<distro>` directory.
