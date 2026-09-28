<p align="center"><img src="assets/icon.png" width="72" alt="OpenFOAM Friend logo"></p>

**Language:** **English** | [中文](README.zh-CN.md)

# OpenFOAM Friend

A Windows desktop workbench for geometry, mesh design, OpenFOAM execution and scientific post-processing.

面向 Windows 的科研桌面工作台，串联几何建模、网格设计、OpenFOAM 求解与科学后处理。

**Authors:** zongxuan & hanwen · **Version:** 0.17.0 · **License:** [GPL-3.0-or-later](LICENSE)

[Download](https://mkdhxy.github.io/OpenFOAMFriend/) · [Releases](https://github.com/MKDHXY/OpenFOAMFriend/releases/tag/v0.17.0) · [Help](https://mkdhxy.github.io/OpenFOAMFriend/help.html) · [Questions and suggestions](https://github.com/MKDHXY/OpenFOAMFriend/issues) · [Full license](LICENSE)

### Bring your OpenFOAM workflow into one visual workspace

**Design geometry → Build a mesh → Run in parallel → Inspect and export**

**[Download FULL](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_FULL_v0.17.0_windows_x64.zip)** · **[Download LITE](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_LITE_v0.17.0_windows_x64.zip)** · [Quickstart](https://mkdhxy.github.io/OpenFOAMFriend/quickstart_EN.html)

![OpenFOAM Friend actual geometry workbench](docs/media/showcase/workbench_en.png)

| Design and mesh | Run and manage | Research and data |
| --- | --- | --- |
| Dimensioned sketches, manual topology, blockMesh / Gmsh, uniform and graded spacing | WSL environment, CPU budgets, PIMPLE, model settings and task queue | Mesh quality, saved-field visualisation, CSV / GIF / MAT / .foam exports |

## See it in action

### Draw geometry. Control the mesh.

Keep the model and flow domain visible while editing nodes, lines, arcs and regions. Assign edge divisions, graded spacing and boundary patches, with guided and expert workflows.

![Manual cylinder topology with region and edge controls](docs/media/showcase/manual_mesh_en.png)

### Inspect real meshes and saved fields

Review mesh quality and locate offending faces. Switch velocity, pressure or vorticity, with adjustable colour maps and saved-field playback. These are example views exported by the application.

| Mesh quality · skewness | Field view · vorticity_z |
| --- | --- |
| [![Actual mesh quality view](docs/media/showcase/mesh_quality.png)](docs/media/showcase/mesh_quality.png) | [![Three-dimensional vorticity view](docs/media/showcase/vorticity_view.png)](docs/media/showcase/vorticity_view.png) |

### Submit, queue and monitor

Choose a CPU budget and track each case's stage, simulated time, latest Courant number and logs. Pause, continue or recover a checkpoint. The queue below contains real workflow-test cases.

![Actual OpenFOAM task queue](docs/media/showcase/solver_queue_en.png)

### Keep your OpenFOAM files within reach

Browse mesh, solver, physical-property and initial-field dictionaries. Edit with line numbers, formatting, structure checks and parameter references.

![OpenFOAM case dictionary editor](docs/media/showcase/dictionary_editor_en.png)

<details>
<summary><strong>More interfaces: scientific exports and SSH / Slurm</strong></summary>

#### Export data for research and PINNs

Export CSV, xytuvp MAT, GIF and complete `.foam` cases from genuinely saved fields.

<img src="docs/media/showcase/exports_en.png" width="440" alt="Loaded real fields and export actions">

#### Configure remote execution

Set the host, identity, remote OpenFOAM environment, partition, CPU count and polling interval, then review the submission script. Your own cluster account is required; production-cluster execution is not yet qualified in this release.

![SSH and Slurm connection configuration](docs/media/showcase/ssh_configuration_en.png)

</details>

Screenshots are recorded application-verification captures and example field views. [Image provenance](docs/media/showcase/provenance.json).

## Download and install

No system Python is needed for either package. Extract the entire ZIP, then double-click `Setup.cmd`. Do not run inside the ZIP or copy a launcher alone.

| Package | Download | Intended computer |
| --- | --- | --- |
| FULL | [Windows x64 · complete offline environment](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_FULL_v0.17.0_windows_x64.zip) | Includes app-local Python/Qt/VTK/Gmsh, signed Microsoft WSL MSI, and a clean Ubuntu24.04 image with OpenFOAM14 and OpenMPI. |
| LITE | [Windows x64 · app and diagnostics](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/OpenFOAMFriend_LITE_v0.17.0_windows_x64.zip) | Includes the same Windows runtime. Missing WSL/OpenFOAM is reported; Linux/system components are never installed. |

[SHA-256 checksums](https://github.com/MKDHXY/OpenFOAMFriend/releases/download/v0.17.0/SHA256SUMS.txt) · [English installation guide](https://mkdhxy.github.io/OpenFOAMFriend/installation_EN.html) · [Chinese installation guide](https://mkdhxy.github.io/OpenFOAMFriend/installation_ZH.html)

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

[English manual](docs/manual_EN.html) · [Chinese manual](docs/manual_ZH.html) · [English quickstart](docs/quickstart_EN.html) · [Chinese quickstart](docs/quickstart_ZH.html) · [Report a reproducible issue](https://github.com/MKDHXY/OpenFOAMFriend/issues/new/choose) · [Help website](http://spaceaero.space)

## Run from source

For developers with Python3.12 x64:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Use the packaged FULL installer for a prepared Linux environment, or configure your existing Foundation14 distribution under WSL connection settings. See [BUILDING.md](BUILDING.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License and attribution

[Full license](LICENSE) · [Bilingual license guide](LICENSE_GUIDE.md) · [Third-party notices](NOTICE)

Application: [GPL-3.0-or-later](LICENSE). Authors: **zongxuan and hanwen**. Dependencies retain their original terms; see [NOTICE](NOTICE). OpenFOAM Friend is independent and is not endorsed by upstream projects. Cite software metadata in [CITATION.cff](CITATION.cff).
