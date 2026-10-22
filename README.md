# OpenCaliper

**An open-source data viewer and analyzer.**

OpenCaliper is a Python desktop application for exploring recorded signals in the time and frequency domains. Load measurement files, arrange signals in plots, compare values with differential cursors, calculate FFT spectra and statistics, and convert supported file formats. Its Python API and command-line tools share the same import and analysis functions.

![OpenCaliper workspace displaying synthetic example signals](docs/images/workspace.png)

## Documentation

Start with the [step-by-step user guide](docs/USER_GUIDE.md). Contributors can follow the [architecture overview and diagrams](docs/ARCHITECTURE.md), then the [developer walkthrough](docs/DEVELOPMENT.md) for API examples, debugging and extension points. The [documentation index](docs/README.md) links all guides, including the [command line](docs/COMMAND_LINE.md), [Python API](docs/PYTHON_API.md), [workspace schema](docs/WORKSPACE_FORMAT.md), and [converter extension guide](opencaliper/converterscripts/README.md). Generate the [Doxygen API reference](docs/DOXYGEN.md) for linked classes, functions, source listings and architecture drawings.

## Features

- File-based Variable Explorer with filtering and drag-and-drop signal selection.
- Multiple analysis tabs and resizable subplots with linked horizontal axes.
- Shared or separate Y axes, configurable curve colors and plot backgrounds.
- Mouse-wheel and rectangle zoom, panning, and fit-to-data controls.
- Differential cursors for time, frequency and amplitude measurements.
- ESRP receiver MAT spectra (`freq`, `avg`, `pk`, `qpk`) open directly in a Spectrum tab.
- Plot-local signal names configurable from the right-click menu.
- FFT analysis tabs with drag-and-drop input, selectable source intervals, and logarithmic axes.
- Minimum, maximum, peak-to-peak, mean, RMS and standard deviation.
- Portable workspace save/restore with embedded recordings and derived channels.
- Signal math, calculus, zero-phase filtering and recording alignment.
- Interval annotations, threshold/peak/pulse/outlier detection and spectrograms.
- PNG, SVG and PDF plot export with cursor measurements; undo and redo.
- Memory-mapped NumPy input for large recordings, with display downsampling.
- GUI, command-line and Python interfaces for supported imports and conversions.

## Easy start on Windows and Linux

Download and extract the source folder, or clone the repository. Keep the complete folder together. Install **Python 3.10 or newer** first; Python 3.12 is a tested choice.

**Windows:** install Python with the Python launcher (`py`) or select **Add Python to PATH** during installation. Double-click **`start_opencaliper.bat`**.

**Linux:** open a terminal in the extracted folder and run:

```bash
./start_opencaliper.sh
```

If the executable permission was lost when extracting a ZIP, use `sh start_opencaliper.sh`. Python must include `pip` and `venv`; on Debian/Ubuntu these are available through `sudo apt install python3 python3-venv python3-pip`. A desktop session and the Qt runtime libraries are required; minimal Linux systems may need additional system libraries.

Both launchers create a local `.venv`, install the application and dependencies on first launch, and open the GUI. First setup requires internet access and may take a few minutes. Later starts reuse the environment; changes to `pyproject.toml` trigger installation again. No environment activation is needed. Use the launcher for your operating system; virtual environments cannot be shared between Windows and Linux.

You can also pass measurement files, or drag a file onto the Windows batch launcher:

```bat
start_opencaliper.bat "C:\Measurements\capture.mat"
```

```bash
./start_opencaliper.sh examples/example.mat
```

### Use an already installed Python environment (without `.venv`)

You can use either approach: the launchers above manage an isolated project `.venv`, while the `start_opencaliper_no_venv` launchers use your current Python environment. Both require Python 3.10 or newer. Installing into an existing environment may update shared dependencies to satisfy the versions in `pyproject.toml`; use the `.venv` option if you want to keep those dependencies isolated.

From a terminal in the project folder, install OpenCaliper and its dependencies once into your chosen Python environment:

**Linux:**

```bash
python3 -m pip install -e .
./start_opencaliper_no_venv.sh
```

**Windows Command Prompt:**

```bat
python -m pip install -e .
start_opencaliper_no_venv.bat
```

If Windows only provides the `py` launcher, use `py -3 -m pip install -e .` instead. If Linux only provides `python`, use `python -m pip install -e .`. The new launchers prefer `python` on PATH, falling back to `python3` on Linux or `py -3` on Windows. Make sure the interpreter used for installation is the same one selected by the launcher. You can always launch explicitly with `python3 -m opencaliper gui` or `py -3 -m opencaliper gui` to choose that interpreter.

These launchers do not create or activate `.venv`, or install packages. If an environment is already activated, they use its Python; deactivate the project's `.venv` first if you want to use your regular Python installation. Some Linux distributions block pip installation into the system-managed Python; in that case use the `.venv` option or another existing environment that permits package installation.

The editable installation (`-e .`) uses this source folder, so keep it in place. Repeat the install command if project dependencies change. If executable permission was lost, use `sh start_opencaliper_no_venv.sh`. File arguments and Windows drag-and-drop work with these launchers too:

```bash
./start_opencaliper_no_venv.sh examples/example.mat
```

```bat
start_opencaliper_no_venv.bat "C:\Measurements\capture.mat"
```

After installation, `python -m opencaliper gui` and the command-line commands below also work in that environment.

### Run the GUI directly with Python

[`run_opencaliper.py`](run_opencaliper.py) lives in the top-level project folder, beside this README and above the `opencaliper` package. After installing dependencies into your chosen Python environment with `python -m pip install -e .`, launch it from a terminal or run it in your IDE:

```bash
python run_opencaliper.py
python run_opencaliper.py examples/example.mat
```

Use `python3` on Linux or `py -3` on Windows if that is your chosen interpreter. This script uses the Python that runs it; it does not create or activate `.venv` or install packages. You can also explicitly use the project environment with `.venv/bin/python run_opencaliper.py` on Linux or `.venv\Scripts\python.exe run_opencaliper.py` on Windows.

You can run the script by its full path from another directory. Relative measurement paths are resolved against your terminal's current directory. In an IDE, select the Python environment containing the dependencies and run this top-level script.

### Manual installation in `.venv` and command line

For developers or command-line use on Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
opencaliper gui
```

On Windows Command Prompt:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -e .
opencaliper gui
```

In PowerShell, activate with `.venv\Scripts\Activate.ps1`, or call `.venv\Scripts\python.exe -m opencaliper gui` directly. Command-line analysis and conversion also work without a graphical display.

## Try the example

[example.mat](examples/example.mat) contains four synthetic voltage channels in the usual acquisition MAT layout. Open it directly:

```bash
opencaliper gui examples/example.mat
```

[example.py](examples/example.py) shows exactly how to construct the file, including channel arrays, units and timing metadata. To regenerate it, or create another copy:

```bash
python examples/example.py
python examples/example.py --output another-example.mat
```

The script replaces the selected output file. No measurement hardware is required. Private recordings and local scripts belong in `measFiles/`, which is excluded from Git and source packages.

## ESRP receiver spectra

MAT files with a `freq` vector and any of `avg`, `pk`, or `qpk` are recognized as frequency-domain data. Opening one immediately plots **Average**, **Peak**, and **Quasipeak** in a **Spectrum** tab, without computing an FFT. Row and column vectors and MATLAB v7.3 files are supported.

Frequency values default to Hz. An optional `freq_unit` field can specify Hz, kHz, MHz or GHz. Amplitudes are preserved as supplied; optional `unit` or detector-specific `avg_unit`/`pk_unit`/`qpk_unit` fields provide their units. Without that metadata, amplitude units remain unspecified. Spectrum plots default to logarithmic X and linear Y so negative dB levels remain visible.

Right-click a curve or its sidebar entry and choose **Rename signal…** to change its plot label. Names are local to the subplot and are retained in saved workspaces.

## Compatible MAT input

The usual acquisition convention stores channels as top-level variables `Channel1_t1`, `Channel2_t1`, and so on. Despite the suffix, these arrays contain **amplitude samples**, not time vectors. OpenCaliper displays them as `Channel1`, `Channel2`, etc.

| Variable | Meaning |
| --- | --- |
| `points` | Number of samples in every channel |
| `xinc` | Sample interval in seconds |
| `xorg`, `xref` | Time origin and reference sample index |
| `ChannelN_t1` | Row or column vector of physical amplitudes, normally float32 |
| `ChannelN_unit` | Unit, for example `VOLT` |
| `ChannelN_yinc`, `ChannelN_offset` | Scaling metadata; applied only to raw unsigned integer samples |
| `date`, `time` | Acquisition timestamp; use `YYYY-MM-DD` and `HH:MM:SS` |
| `samplerate`, `count`, `format` | Additional acquisition metadata |

All channels use the shared time vector:

```python
time = xorg + (np.arange(points) - xref) * xinc
```

For floating-point channel arrays, samples are already in physical units and are not scaled again. Raw `uint8`/`uint16` arrays are also supported with their scaling metadata. `xinc` determines the stored sample interval; `samplerate` does not override it.

To import another file type, convert its physical samples and timing into this layout. See [the MAT format guide](docs/MAT_FORMAT.md) for field details, raw scaling, a converter example and MATLAB code. Both classic MATLAB files and MATLAB-compatible HDF5 files are supported. MAT exports additionally preserve arbitrary names and independent per-channel time vectors in OpenCaliper's interchange layout.

## Using the viewer

1. Open a measurement or drop files into the **Variable Explorer**. Expand a file with **+** to see its channels.
2. Drag channels into a plot. Double-clicking a channel adds it to the first plot of the active tab.
3. Use **Add plot** for another subplot or **New analysis** for an independent time-domain tab.
4. Drag plot dividers to adjust sizes. Use **Pan**, **Rectangle zoom**, the mouse wheel, or **Fit both axes** to navigate.
5. Enable **Diff cursors** and left-click in a plot to place A, then B (alternating). Drag either cursor to adjust it. Click placement also recovers cursors outside a zoomed view. Cursor positions are shared within a tab.

Select entries beside a plot and press **Delete** to remove those curves. **Clear plot** removes all curves in that subplot; **×** removes the subplot itself. Deleting a file entry in the Explorer unloads its signals from all tabs without deleting the file on disk.

Right-click a signal to change its color or choose a main, separate, or shared Y axis. Right-click empty plot space for signal-color and background-color options. Colors are local to each subplot and retained during that subplot's running session.

### FFT and statistics

**FFT** opens a frequency-domain tab. Drag signals into its plots to calculate spectra; an already selected signal is added when the tab opens. FFT uses a Hann window, removes the mean and displays one-sided peak amplitude in the original signal unit. **Log X** and **Log Y** are enabled by default. Nonpositive coordinates are hidden on logarithmic axes; the underlying samples remain available when switching back to linear display.

If time-domain cursors are enabled when FFT opens, their interval becomes the source time interval. Otherwise, the full signal is used. Edit **Time interval** and click **Recalculate** to update all spectra in that tab. Frequency-domain cursors measure Hz, Δf and interpolated amplitudes independently of the source time interval. Logarithmic amplitude display does not convert values to decibels.

**Statistics** analyzes the selected signal or spectrum, using the current tab's cursor interval when enabled. Time cursors report seconds, Δt, 1/|Δt| and interpolated signal differences. Outside the recorded range, interpolated values are unavailable and shown as NaN. Statistics ignore nonfinite samples; FFT requires at least four finite real samples. For uneven timestamps, enable **Resample (linear)** in the FFT tab, leave the sample rate at **Auto** or enter Hz, and click **Recalculate**. Source data stays unchanged; interpolation estimates a uniform grid and does not add measured bandwidth.

## Command line

```bash
opencaliper info measurement.mat
opencaliper stats measurement.mat --signal 0 --start 0 --stop 0.5
opencaliper fft measurement.mat spectrum.csv --signal 0
opencaliper convert measurement.mat measurement.mf4
opencaliper convert measurement.mat measurement.raw
opencaliper convert measurement.mat measurement.wvf
opencaliper convert recording.mf4 converted.mat
```

`--signal` is the zero-based channel index printed by `info`; interval values are seconds. `python -m opencaliper` provides the same commands. `mat2raw input.mat output.raw` is a shortcut for RAW conversion. Converters refuse to overwrite files unless `--overwrite` is supplied; FFT CSV output also refuses existing files.

## Converter scripts and adding formats

All import/export adapters live in [`opencaliper/converterscripts/`](opencaliper/converterscripts/README.md), with separate files such as `mdfconvert.py`, `wvfconvert.py`, `rawconvert.py`, `matexport.py` and `mdfexport.py`. A central dispatcher detects the extension and chooses the adapter. The viewer and CLI use this same registry.

```bash
python -m opencaliper.converterscripts recording.mf4
python -m opencaliper.converterscripts recording.wvf recording.mat
python opencaliper/converterscripts/convert.py recording.raw recording.mat
```

Without an output argument, conversion creates `recording.opencaliper.mat`, the native OpenCaliper interchange layout. It preserves physical samples, independent channel time axes, names, units and acquisition timestamp. Other registered export formats can be selected through the output extension. Existing outputs require `--overwrite`.

The [converter guide](opencaliper/converterscripts/README.md) documents the expected `Recording`/`Signal` objects, MAT fields, adapter functions and a contributor example. Add a reader/exporter and register its extension in `formats.py`; the GUI file pickers update automatically.

## File support

| File type | Import | Export |
| --- | --- | --- |
| NumPy `.npy` (time column followed by channel columns) | Yes, memory-mapped | No |
| MATLAB `.mat` (documented acquisition and OpenCaliper layouts) | Yes | Yes |
| MDF `.mdf` / `.mf4` | Yes | Yes |
| Keysight `.bin` | Yes | No |
| Yokogawa `.wvf` + companion `.hdr` | Yes | Yes |
| LTspice `.raw` | Yes | Yes |

Readers support numeric waveform data within these formats: Keysight normal/average float32 time waveforms, Yokogawa single-block IS2 data, MDF numeric scalar channels, and LTspice time-domain recordings with one plot per file. Compatibility depends on the file's encoding, not only its extension.

### Workspace and signal tools

The **Workspace** menu saves and opens portable `.ocw` sessions and exports individual plots as PNG, SVG or PDF. Sessions contain source samples, derived channels, tabs, curve colors, axes, plot ranges, cursors and annotations. **Edit → Undo/Redo** restores structural edits and processing actions.

The **Signal tools** menu provides arithmetic expressions (`CH0 - CH1`, `integrate(CH0)`), filtering, manual/edge/correlation alignment, annotations, event detection and spectrograms. Results become additional channels for comparison. See [the detailed workflow](docs/USER_GUIDE.md#workspace-and-signal-tools) for settings and requirements.

### Current limits

Most recording formats are loaded into memory; `.npy` input uses memory mapping. Imports run in background threads, while FFT calculation and export currently run on the interface thread. Large recordings can take time and memory. Save `.ocw` workspaces to retain analysis tabs between sessions.

RAW and WVF export require real channels on identical, uniformly spaced time axes. RAW export requires finite voltage/current data and starts time at zero; its header records the original time origin. WVF output uses int16 quantization. Conversion does not preserve all device-specific metadata. MDF numeric state channels with text labels are plotted using their numeric codes; numerical gain/offset conversions still apply. Files with no supported numeric scalar channels report an error. Text, structured and bus-decoding channels are outside the current MDF import scope. See [the format guide](docs/MAT_FORMAT.md) for additional input limits.

## Development

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python -m build
```

To generate the API reference and architecture drawings, install Doxygen and Graphviz, then run from the repository root:

```bash
doxygen Doxyfile
```

Open `docs-api/html/index.html` in your browser. These documentation tools are optional and are not installed by the application launchers. See the [Doxygen guide](docs/DOXYGEN.md) for Linux and Windows setup. The documentation workflow also provides a downloadable HTML artifact in GitHub Actions; no documentation website is published automatically.

Tests use generated data and temporary files. Optional local capture fixtures can be supplied with `OPENCALIPER_TEST_DATA_DIR`; see [CONTRIBUTING.md](CONTRIBUTING.md). The CI workflow runs the automated tests and builds release artifacts.

## License

OpenCaliper is distributed under **GPL-3.0-only**. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Dependencies retain their own licenses. The software is provided without warranty as described in the license.
