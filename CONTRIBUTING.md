# Contributing to OpenCaliper

Bug reports, documentation improvements, format adapters and analysis features are welcome.

Before changing code, read the [architecture overview](docs/ARCHITECTURE.md) and [developer guide](docs/DEVELOPMENT.md). They explain the data model, GUI state ownership, call flows, test map and common extension points. For application behavior, see the [user guide](docs/USER_GUIDE.md).

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
```

GUI tests use Qt's offscreen platform. On a minimal Linux system, install the Qt runtime system libraries required by the PySide6-Essentials wheel, including EGL/OpenGL libraries. Python dependencies are declared in `pyproject.toml`.

## API documentation

The [Doxygen guide](docs/DOXYGEN.md) explains how to install the optional Doxygen and Graphviz tools and build the HTML API reference. From the repository root:

```bash
doxygen Doxyfile
```

Open `docs-api/html/index.html` and check that `docs-api/warnings.log` is empty. Keep docstrings aligned with behavior; document units, constraints, return values and side effects next to public functions. When changing dependencies, ownership or loading flow, update both the [architecture guide](docs/ARCHITECTURE.md) and [Doxygen drawings](docs/doxygen/architecture.dox). Update the user guide for user-visible behavior.

Commit documentation sources rather than generated `docs-api/` output. The [documentation workflow](.github/workflows/documentation.yml) builds the reference and uploads a browsable HTML artifact for review. Application and documentation checks are separate workflows.

## Changes

- Describe the problem and intended behavior in an issue or pull request.
- Keep the change focused and update documentation for changed behavior.
- Add regression coverage for parser, numerical or interaction changes when appropriate. Use synthetic fixtures and independent expected values for numerical tests.
- Keep imports, conversions and analysis callable independently of the GUI.
- Document scaling, units, timing and unsupported cases for file-format adapters. Do not silently invent metadata or resample inputs.
- Be respectful and constructive in issues and reviews.

By contributing, you agree that your contributions may be distributed under the project's GPL-3.0-only license. Submit only material you have the right to contribute, and retain required third-party notices. Do not copy proprietary code, assets or confidential measurements into a contribution.

## Test data

The public tests generate their own numeric signals and temporary files. Do not attach or commit company, customer, personal or otherwise restricted recordings. Reproduce issues with synthetic or explicitly publishable data and redact local paths, hostnames, network addresses and device identifiers from logs.

To run optional local capture tests, set `OPENCALIPER_TEST_DATA_DIR` to a directory containing any of `sample.mat`, `sample.bin`, `sample.wvf` with `sample.hdr`, and `sample.mf4`. An optional `sample.wdf`/`sample.wvf` pair is used by the standalone converter regression tests. These files remain local and are not required by CI.

## Source layout

- `opencaliper/core.py`: signal model, imports and exports.
- `opencaliper/analysis.py`: numerical analysis.
- `opencaliper/gui.py`: desktop workspace and interaction.
- `opencaliper/cli.py`: command-line entry points.
- `opencaliper/acquisition.py`, `opencaliper/raw.py`: acquisition-layout and waveform export helpers.
- `examples/example.py` and `examples/example.mat`: synthetic acquisition-layout example.
- `measFiles/`: ignored local recordings and utilities; never included in packages.
- `Doxyfile`: API extraction and Graphviz configuration.
- `docs/`: user, architecture, development, MAT-format and release guides.
- `docs/doxygen/`: reference landing page and architecture drawing sources.
- `docs-api/`: generated HTML, SVG diagrams and warning log; ignored by Git.
