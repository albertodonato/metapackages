# Repository with metapackages

[![Build status](https://github.com/albertodonato/metapackages/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/albertodonato/metapackages/actions?query=workflow%3ACI+branch%3Amain)

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
