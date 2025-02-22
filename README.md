# Build repository with metapackages

This builds metapackages to automatically install all desired dependencies on a
Linux distribution.

Supported distributions:

- Arch Linux
- Ubuntu


## Dependencies
------------

Python dependencies for the script can be installed via

```bash
pip install -r requirements.txt
```


## Build

Packages and repository are built via

```bash
./repository build
```

Result is in the `repo/<distro>` directory.
