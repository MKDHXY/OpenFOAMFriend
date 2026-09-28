# Building release bundles

Source and offline runtime distributions are separate. The Git repository does not contain large binaries or a personal WSL export.

1. Copy this source into a dated version directory `vYYYYMMDD_HHMMSS` under an empty build root. Keep `requirements.txt` pinned.
2. Create sibling `installer_cache/wheels` using a Python3.12 x64 build interpreter (`pip download -r requirements.txt -d installer_cache/wheels`). `tools/download_installer_assets.py` downloads official embedded CPython, canonical Ubuntu rootfs and Microsoft WSL MSI with publisher hashes.
3. Run `tools/build_portable_runtime.py` from the version directory. It embeds dependencies, Gmsh DLL and Microsoft C++ DLLs; `python312._pth` disables user/global site packages.
4. Provision only a fresh dedicated WSL distribution with `installer/provision-linux.sh`. Never export a personal research distribution. Review `clean-linux-image.sh` before running it in the dedicated build distro, terminate that distro and export it to sibling `installer_cache/openfoam14-ubuntu24.04.tar`.
5. Compress using `tools/compress_linux_image.py`; fetch component-source archives with `tools/download_component_sources.py`. Supply the official OpenSSH client asset plus its hash metadata if building the SSH-capable bundle (see released asset_sources.json).
6. Run `tools/build_offline_packages.py`; provide current verification evidence, then archive with SHA256/CRC verification. Use a new empty recipient profile and isolated PATH for installation acceptance. Repeat real approximately5000-cell/four-rank 3D CFD pipelines and export checks.

The scripts reflect the v0.17 build pipeline, not a universal cross-platform installer. WSL feature enablement/reboot on a physical cold machine still requires qualification. Do not claim offline Windows OS-component repair or production-cluster qualification.
