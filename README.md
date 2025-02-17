Script to build ditribution metapackages and a repository for them
==================================================================

This builds metapackages to automatically install all desired dependencies on a
Linux distribution.


Dependencies
------------

Python dependencies for the script can be installed via

```bash
pip install -r requirements.txt
```


Build
-----

Packages and repository are built via

```bash
./repository build
```

Result is in the `repo/<distro>` directory.

Currently supported distributions (autodetected) are *Ubuntu* and *Arch Linux*.


Copy
----

The resulting repository is copied via `rsync` via:

```bash
./repository copy <host>
```

SSH configuration for the host needs to be set up. By default, the repo is
copied under the Nginx root directory.
