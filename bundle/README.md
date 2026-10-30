# Single-file executable builds

## Linux executable

Build on Linux using the architecture you intend to distribute (for example,
x86-64). From the project root:

```sh
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -e '.[linux-build]'
.venv-build/bin/python scripts/build_linux.py
./dist/OpenCaliper
```

The result is a single executable named `OpenCaliper`, including Python, Qt,
converters, scientific libraries, the logo and license notices. Recipients can
run `chmod +x OpenCaliper` if downloading removed its executable permission,
then `./OpenCaliper`. Measurement paths can be passed as arguments.

Linux builds depend on the host's glibc and desktop graphics libraries; they are
not universal across all Linux distributions or CPU architectures. The local
x86-64 artifact was built on Ubuntu 24.04 with glibc 2.39. Use a compatible system
and verify it there; build on an older supported distribution if older glibc
support is needed. A graphical desktop and Qt platform dependencies are still
required. No Python installation or virtual environment is needed to run it.

Test the packaged application with:

```sh
QT_QPA_PLATFORM=offscreen ./dist/OpenCaliper --self-test /tmp/opencaliper-test.json
cat /tmp/opencaliper-test.json
sha256sum dist/OpenCaliper
```

The test must exit successfully and report `"status": "ok"` and `"frozen": true`.
The builder accepts `--output` and `--work` paths. Linux and Windows share the
specification and bundled self-test below; each must be built on its target OS.

## Windows executable

The release target is `dist/OpenCaliper.exe`: one Windows 10/11 x64 GUI executable
including Python, Qt, scientific libraries, file adapters, the logo and notices.
Recipients do not install Python or activate an environment.

Builds must use Windows Python. The supported release build runs on a native
Windows machine or the **Windows executable** GitHub Actions workflow. A Windows
Python environment under Wine can produce an additional local test artifact, but
Wine testing is not a substitute for checking the release on native Windows.

## Build locally on Windows

The build extra selects the validated Qt 6.11 line (`<6.12`). Use 64-bit Python 3.12 and an extracted checkout, from Command Prompt:

```bat
py -3.12 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -e ".[windows-build]"
.venv-build\Scripts\python.exe scripts\build_windows.py
```

The output is `dist\OpenCaliper.exe`. Double-click it, or drag measurement files
onto it. It starts the GUI without a console window. The application icon is
embedded in the executable. Do not run the builder using a Linux Python and
rename the resulting binary to `.exe`.

Use `--output path` and `--work path` to change output/work directories. Builds
replace the output executable. All runtime modules come from the selected Python
environment, so use a clean build environment for releases.

## GitHub Actions

1. Push the build recipe and application changes to GitHub.
2. Open **Actions → Windows executable → Run workflow** and select the branch.
3. Wait for the application tests, binary build and executable smoke test to pass.
4. Download the **OpenCaliper-Windows-x64** artifact and extract it.
5. Test `OpenCaliper.exe` on native Windows. Manual runs produce artifacts only.

Version tag pushes matching `v*` or `OpenCaliperV*` trigger a build and, after all tests succeed,
automatically publish a GitHub Release with `OpenCaliper.exe`, its SHA-256 checksum
and dependency inventory attached. Users download the EXE directly from
**Releases → Assets**, without navigating Actions or extracting an artifact ZIP.
Existing releases receive missing assets; reruns preserve files already uploaded
and leave an existing release's draft/published status unchanged.

Commit and push the workflow first, then tag the intended commit, for example:

```sh
git tag -a v0.1.1 -m 'OpenCaliper 0.1.1'
git push origin v0.1.1
```

Choose an unused version and update `pyproject.toml` and `CHANGELOG.md` first.
Only the EXE is needed to run. Linux currently has a local builder only; attach
its executable manually if you want it included in the same release.

## Verify the actual executable

Because a windowed EXE has no normal stdout, the smoke test writes JSON. In
PowerShell:

```powershell
$p = Start-Process -FilePath "$PWD\dist\OpenCaliper.exe" -ArgumentList '--self-test', "$PWD\self-test.json" -Wait -PassThru
Get-Content self-test.json
if ($p.ExitCode -ne 0) { throw 'Executable smoke test failed' }
```

Use a report path without spaces in this abbreviated example; the workflow quotes
paths containing spaces. A successful report has `"status": "ok"`. It exercises
registered converters (including MDF/MF4, RAW, WVF/HDR, Keysight BIN, NPY and v7.3
MAT), Keysight HDF5, Touchstone S2P/S4P, measured receiver spectra, FFT, S Parameter
pages and Smith charts, visibility controls, the GUI logo,
PNG/SVG/PDF export and workspace save/restore. It generates synthetic temporary
data and does not open private measurements.

## Contents and release behavior

- `OpenCaliper.spec` uses PyInstaller one-file mode and collects dynamically
  selected converter modules, package assets and dependency metadata.
- `scripts/frozen_entry.py` dispatches to `opencaliper.frozen.main()`; normal
  arguments are measurement files, while `--self-test report.json` runs validation.
- Built-in PyInstaller hooks collect Qt plugins and the NumPy/SciPy/HDF5 libraries.
  Unused alternative Qt bindings and the Tk backend are excluded.
- `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md` and dependency metadata are embedded.
  **Help → About OpenCaliper** and **Help → Licenses and notices** expose version,
  source location and available license texts without a network connection.
- The executable extracts its supporting files into a temporary directory at
  startup. The first launch can therefore take longer than a normal installation.
  File parsing and analysis retain the same memory/format limits as the source app.
- Builds are unsigned unless you sign the finished executable separately with
  your own Windows signing certificate. No certificate or signing key is stored
  in this repository. Record the checksum after any signing step.
- Share the matching source/version and required notices with the release; see
  [release guidance](../docs/RELEASING.md). Bundling does not preserve arbitrary
  device metadata or change the documented converter support.

PyInstaller is a build-time dependency only. The spec collects application data,
not the `.venv`, examples folder, tests, workspace files or local recordings.
The process records the resolved dependencies; identical source does not promise
bit-for-bit identical binaries across build environments.

References: [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html),
[spec files](https://pyinstaller.org/en/stable/spec-files.html), and
[hook configuration](https://pyinstaller.org/en/stable/hooks-config.html).
