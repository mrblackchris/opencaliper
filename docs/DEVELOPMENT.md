# Developer guide

This guide takes you from a checkout to a small working example and shows where to implement changes. Read [Architecture](ARCHITECTURE.md) alongside it for state ownership and call flows.

## 1. Set up a development environment

From the repository root on Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
```

On Windows Command Prompt:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
```

The editable installation makes source changes available on the next application start without rebuilding a package. The `dev` extra adds the package build tool. Test commands assume the repository root is the working directory. GUI tests select Qt's offscreen platform; minimal Linux systems still need Qt runtime system libraries.

Normal users can use the [launchers](../README.md#easy-start-on-windows-and-linux) instead. They install the application in `.venv` automatically. `scripts/launch.py` compares a stored hash of `pyproject.toml` before deciding whether to run pip again; source edits need no reinstallation with an editable install. If an environment becomes damaged, recreate `.venv` with the development commands above. Do not reuse an environment copied from another operating system.

## 2. Follow a recording through the Python API

Save this snippet as a temporary script in the repository root, or run it interactively in the activated environment:

```python
from pathlib import Path
import numpy as np
from opencaliper import Recording, Signal, load, export
from opencaliper.analysis import fft, statistics, cursor_values

recording = load('examples/example.mat')
signal = recording.signals[0]
print(signal.name, signal.unit, len(signal.values))
print(statistics(signal))
print(cursor_values(signal, -0.0005, 0.0005))
frequency, amplitude = fft(signal)
peak = int(np.argmax(amplitude))
print('Largest FFT bin:', frequency[peak], 'Hz;', amplitude[peak], signal.unit)

# A new signal on the same axis, without changing the original values.
scaled = Signal('Half amplitude', signal.time.copy(), signal.values * 0.5, signal.unit)
output = Recording([scaled], timestamp=recording.timestamp)
export(output, Path('derived.mat'))
```

`derived.mat` must not already exist; pass `overwrite=True` only when replacement is intended. The FFT's largest bin is near the example's 10 kHz fundamental; finite record length determines the exact bin spacing. No GUI objects are required by this snippet.

Read these definitions in order:

1. `Signal` and `Recording` in [core.py](../opencaliper/core.py): the objects passed between components.
2. `load()` in `core.py`, the dispatcher in [converterscripts/convert.py](../opencaliper/converterscripts/convert.py), and [matconvert.py](../opencaliper/converterscripts/matconvert.py): file-to-model conversion.
3. `load_mat()` and `read_measurement()` in [acquisition.py](../opencaliper/acquisition.py): storage detection and physical scaling.
4. `statistics()`, `fft()` and `cursor_values()` in [analysis.py](../opencaliper/analysis.py): numerical behavior.
5. `main()` in [cli.py](../opencaliper/cli.py): these same calls from the command line.
6. `Loader`, `Window.loaded()`, `Window.add_signal()` and `Window.transformed_signal()` in [gui.py](../opencaliper/gui.py): file loading through to displayed curves.

For domain-aware examples, processing contracts and explicit FFT resampling, see
[the Python API guide](PYTHON_API.md). The [workspace schema](WORKSPACE_FORMAT.md)
documents persisted state, optional defaults and migration responsibilities.

## 3. Run and debug

```bash
python -m opencaliper info examples/example.mat
python -m opencaliper stats examples/example.mat --signal 0
python -m opencaliper gui examples/example.mat
```

For an IDE, select a Python environment with the dependencies installed and run the top-level `run_opencaliper.py`, optionally with `examples/example.mat` as an argument. Alternatively launch the module `opencaliper` with arguments `gui examples/example.mat`. Relative measurement paths use the working directory. The [startup guide](../README.md#run-the-gui-directly-with-python) also covers the managed `.venv` and existing-environment launchers.

Useful breakpoint locations:

| Symptom | Start inspecting |
| --- | --- |
| File rejected or wrong scaling | `core.load()`, then `acquisition.read_measurement()` or the relevant reader |
| File loaded but missing from explorer | `Window.loaded()` and its `signals`/`files` registries |
| Dropping a channel adds nothing | `MeasurementExplorer.mimeData()`, `Plot.dropEvent()`, `Window.add_signal()` |
| Incorrect spectral amplitude | `analysis.fft()` before any plotting |
| Cursor looks wrong only on log axes | `Plot.x_to_scene()`, `Plot.x_from_scene()`, `Window.move_cursor()` |
| Curve appears on wrong Y axis | `Plot.assign_axis()` and `Window.update_axis_labels()` |
| File unload leaves a curve | `Window.remove_files()` and `Window.remove_signals()` |
| Launcher fails before GUI opens | Terminal output from `scripts/launch.py`, Python version, pip and venv availability |

Core functions raise exceptions. The CLI prints errors and returns a nonzero exit code; the GUI reports import and interaction failures through dialogs. For a parser problem, reproduce it with `opencaliper info` or `load()` first to separate file decoding from GUI state.

## 4. Where to implement a change

### Add an input format

Create a `read(path) -> Recording` adapter in `opencaliper/converterscripts/` and register the extension in `formats.py`. The [converter guide](../opencaliper/converterscripts/README.md) documents the shared in-memory model, native MAT fields, supported variants and a complete contributor example. Decode physical values and horizontal units explicitly: seconds for `domain="time"`, Hz for `domain="frequency"`. Do not silently resample data.

Add synthetic parser tests, including malformed input and independently calculated scaling/timing expectations. Registering an extension updates API dispatch, CLI conversion and GUI file filters automatically. Format-specific dependencies belong inside adapters and in project dependency metadata where needed.

### Add an output format

Create a writer exposing `write(recording, path, overwrite=False)` and register its module in `formats.py`. Keep overwrite protection, including companion files, and validate format constraints before writing. Exercise the writer using a separate reader or byte-level expectations; a reader and writer with the same faulty formula can pass a round-trip test.

### Add an analysis operation

Implement the numerical function in `analysis.py` or `processing.py` using the shared model and arrays. Decide its rules for intervals, nonfinite data, complex values and nonuniform sampling. Test the expected numeric result independently before wiring it into `cli.py` or a GUI action. If an operation changes the horizontal domain, document its units and avoid confusing it with source timestamps.

### Change a GUI interaction

Identify the owner of the affected state in the [architecture state table](ARCHITECTURE.md#gui-state-and-ownership). A per-plot color belongs to `Plot`; a shared source signal belongs to `Window`; FFT source bounds belong to `AnalysisPage`. Keep cleanup paths consistent when removing curves, files, plots and tabs. Consider switching tabs and displaying the same source in multiple plots when validating the change.

## 5. Test map

Run all tests with `python -m unittest discover -s tests -v`. To focus on an area:

```bash
python -m unittest discover -s tests -p test_core.py -v
python -m unittest discover -s tests -p test_fft_gui.py -v
```

| Test file | Main coverage |
| --- | --- |
| `test_converter_dispatch.py` | Registry extensions, native conversion, CLI/script integration and overwrite checks |
| `test_core.py` | Analysis, supported export/import round trips, independent axes and channel order |
| `test_converters.py` | Acquisition layouts, scaling, waveform headers and quantization |
| `test_raw.py` | Binary RAW precision, layout and invalid output handling |
| `test_example.py` | Bundled/generated MAT fields, physical samples and timing |
| `test_gui.py` | Explorer, plots, removal, navigation, colors and axis interactions |
| `test_spectrum_analysis.py` | Unified toolbar actions, mixed FFT/receiver drops, peak aliases and legacy workspace migration |
| `test_fft_gui.py` | FFT workspaces, intervals, log displays and frequency cursors |
| `test_mat_timestamps.py` | Optional dates, recognized metadata and nonblocking fallback across MAT layouts |
| `test_mdf.py` | Numeric MDF/MF4 conversions, labelled state channels and unsupported files |
| `test_esrp.py` | ESRP vectors, v7.3 MAT, native frequency metadata, auto-plot and plot-local renaming |
| `test_cursor_clicks.py` | A/B click placement, logarithmic axes, subplot synchronization and preserved drag/menu gestures |
| `test_fft_resampling.py` | Known-tone interpolation, Auto/manual rates, retries, CLI and workspace persistence |
| `test_processing.py` | Signal math/calculus, filter response, alignment, events, spectrograms and memory-mapped inputs |
| `test_workspace.py` | Session round trips, source identity, undo/redo, real dialog lifetimes and plot exports |
| `test_launcher.py` | Environment creation, setup reuse/failure and argument forwarding |

Tests use synthetic data. Some optional private-fixture checks skip unless `OPENCALIPER_TEST_DATA_DIR` is set; see [Contributing](../CONTRIBUTING.md#test-data). `measFiles/` stays local and is not a CI dependency. The CI workflow currently tests Linux with Python 3.10 and 3.12; it does not establish Windows execution coverage.

## 6. Build and maintain the documentation

Install Doxygen and Graphviz separately from the Python runtime dependencies; see [Doxygen setup](DOXYGEN.md#install-the-documentation-tools). Run from the repository root:

```bash
doxygen Doxyfile
```

Open `docs-api/html/index.html`. Start with **Architecture drawings**, then browse **Packages**, **Classes** or **Files** to find the implementation and its contracts. The API pages document arguments, returns, units, validation and side effects where provided. The `docs-api/warnings.log` file should be empty after a successful build. Documentation generation does not import or execute application code.

Use ordinary Python docstrings with Doxygen `@param`, `@return` and `@exception` commands for public APIs; `PYTHON_DOCSTRING = NO` enables their interpretation. Keep the comments readable in source. The [Doxygen guide](DOXYGEN.md#documenting-code) contains an example.



When changing behavior, update the user guide; when changing ownership or call paths, update the architecture guide, its Mermaid diagrams and the corresponding Graphviz drawings in `docs/doxygen/architecture.dox`. Keep diagrams close to the code and verify the method names they mention. Review generated or assisted changes against actual behavior, expected numerical results and tests just as you would any other contribution. Architecture diagrams are a navigation aid, not proof that the implementation is correct.

Run `python -m build` for packaging changes and inspect the resulting archives. `MANIFEST.in` includes Markdown guides, `Doxyfile`, the `.dox` diagram/page sources, launchers and the public synthetic example in the source distribution, while excluding `measFiles/`. A wheel includes installable code and the converter adapter guide; the complete onboarding material and root launcher are in the repository/source archive. See [Releasing](RELEASING.md) for distribution checks.

The separate [documentation workflow](../.github/workflows/documentation.yml) generates the reference, checks for warnings and uploads the HTML as an artifact. It does not enable GitHub Pages. Generated `docs-api/` files stay outside Git and release source archives; regenerate them from the checked-in configuration and comments.
