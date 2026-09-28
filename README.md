<p align="center"><img src="assets/icon.png" width="72" alt="OpenFOAM Friend logo"></p>

# OpenFOAM Friend

**A Windows desktop workbench for geometry, mesh design, OpenFOAM execution and scientific post-processing.**

**Authors: zongxuan & hanwen** · **Version: 0.17.0** · **GPL-3.0-or-later**

[English](README.md) · [中文](README.zh-CN.md) · [Bilingual download page](https://mkdhxy.github.io/OpenFOAMFriend/) · [Releases](https://github.com/MKDHXY/OpenFOAMFriend/releases/tag/v0.17.0)

## Download and install

No system Python is needed for either package. Extract the entire ZIP, then double-click `Setup.cmd`. Do not run inside the ZIP or copy a launcher alone.

| Package | Download | Intended computer |
| --- | --- | --- |
| FULL | [Windows x64 · complete offline environment](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_FULL_v0.17.0_windows_x64.zip) | Includes app-local Python/Qt/VTK/Gmsh, signed Microsoft WSL MSI, and a clean Ubuntu24.04 image with OpenFOAM14 and OpenMPI. |
| LITE | [Windows x64 · app and diagnostics](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_LITE_v0.17.0_windows_x64.zip) | Includes the same Windows runtime. Missing WSL/OpenFOAM is reported; Linux/system components are never installed. |

[SHA-256 checksums](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/SHA256SUMS.txt) · [English installation guide](https://mkdhxy.github.io/OpenFOAMFriend/installation_EN.html) · [中文安装指南](https://mkdhxy.github.io/OpenFOAMFriend/installation_ZH.html)

**Requirements:** Windows10 build19041+ or Windows11 on Intel/AMD x64; 10GB free minimum, 15GB+ recommended. FULL first-time WSL enablement needs administrator permission, BIOS/UEFI virtualization and possibly a manual restart. The package does not bypass corporate policy or include the Windows operating system. ARM64/macOS/native Linux GUI builds are not supplied.

Language can be changed directly on the welcome page and in Settings; the installer also supports Chinese/English.

## Workflow

| Stage | Available operations |
| --- | --- |
| Geometry | Dimensioned 2D sketching, two-click lines, arcs/shapes, regions, 3D extrusion preview and camera controls. |
| Meshing | Structured cylinder O-grid, partitioned box, manual topology/blockMesh/Gmsh, triangular/prismatic, quad-dominant and tetrahedral generation; uniform and graded spacing. |
| Quality | Actual `checkMesh` results, skewness/non-orthogonality/aspect ratio, quality thresholds and offending-face locations. |
| Execution | OpenFOAM Foundation14 `foamRun` + `incompressibleFluid`, PIMPLE controls, typed turbulence-model catalogue, CPU-budgeted queue, pause/continue, checkpoint recovery and configurable polling. |
| Results | VTK field views, playback, adjustable colour maps, velocity/pressure/vorticity, complete `.foam` case export, CSV/GIF/MAT and single-sided unwindowed force FFT. |
| Remote | OpenSSH + Slurm configuration, reviewed batch scripts and monitoring. A real remote cluster account is required. |

![Welcome page with language selector](docs/media/welcome_en.png)

## Measured verification

Three fresh 3D cases were executed with **5,120 cells and four MPI ranks**, covering structured O-grid, manual Gmsh topology and `kOmegaSST`. Real MAT/CSV/GIF and reconstructed `.foam` exports were checked for finite fields, genuine times and readable meshes. End times were 0.04/0.06/0.10s; these are workflow tests, **not physical/statistical convergence evidence**.

The clean Linux image was actually imported into independent WSL distributions. App installation in a Chinese/space-containing directory, isolated Python imports, app-local C++ runtime DLLs, welcome-language changes and interface regressions were verified. [Detailed evidence](docs/verification/package_verification.html).

**Qualification boundary:** the physical host was Windows10 19045 x64 with WSL already enabled. A new computer's BIOS/UAC/reboot sequence, all Windows11/GPU combinations and end-to-end submission to a production cluster were not physically tested. This is a research engineering release, not commercial CFD certification or a complete ParaView replacement. The bundled OpenSSH client is the upstream Microsoft preview identified in NOTICE.

## Documentation and support

[English manual](docs/manual_EN.html) · [中文手册](docs/manual_ZH.html) · [English quickstart](docs/quickstart_EN.html) · [中文快速教程](docs/quickstart_ZH.html) · [Report a reproducible issue](https://github.com/MKDHXY/OpenFOAMFriend/issues/new/choose) · [Help website](http://spaceaero.space)

## Run from source

For developers with Python3.12 x64:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Use the packaged FULL installer for a prepared Linux environment, or configure your existing Foundation14 distribution under WSL connection settings. See [BUILDING.md](BUILDING.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License and attribution

Application: [GPL-3.0-or-later](LICENSE). Authors: **zongxuan and hanwen**. Dependencies retain their original terms; see [NOTICE](NOTICE). OpenFOAM Friend is independent and is not endorsed by upstream projects. Cite software metadata in [CITATION.cff](CITATION.cff).
