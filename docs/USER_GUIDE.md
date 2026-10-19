# User guide

Use this walkthrough with the bundled synthetic measurement before opening your own data. It requires no acquisition hardware.

## Start the application

Install Python 3.10 or newer (Python 3.12 is tested), download and extract the complete project, then start the launcher for your platform:

- **Windows:** double-click `start_opencaliper.bat`.
- **Linux:** open a terminal in the project folder and run `sh start_opencaliper.sh`.

The first run creates `.venv` inside the project and downloads dependencies. Wait for installation to finish; the GUI opens afterward. Keep the project in a writable folder. Subsequent runs reuse the environment. If setup fails, read the terminal message; the Windows launcher pauses to keep it visible. More setup options are in the [README](../README.md#easy-start-on-windows-and-linux).

To use an already installed Python environment instead, install with `python -m pip install -e .` from the project folder (use `python3` on Linux if needed), then run `start_opencaliper_no_venv.bat` on Windows or `sh start_opencaliper_no_venv.sh` on Linux. These launchers use your current Python and do not create `.venv` or install dependencies. See the [existing-environment instructions](../README.md#use-an-already-installed-python-environment-without-venv) for interpreter selection and setup details.

To open the example immediately on Linux, run:

```bash
sh start_opencaliper.sh examples/example.mat
```

On Windows, either drag `examples\example.mat` onto the batch launcher or run:

```bat
start_opencaliper.bat examples\example.mat
```

## Load and display signals

1. Click **Open files** and select `examples/example.mat`, or drop the file into the Variable Explorer.
2. Expand the file entry using **+**. Four channel entries appear.
3. Drag `Channel1` into the plot, or double-click the channel to add it to the active tab's first plot.
4. Add another channel to compare traces. The sidebar beside the plot lists the signals displayed there.
5. Use **Fit both axes** if you cannot see the complete trace.

The explorer is shared by all analysis tabs. Its filter searches signal entries. Loading a file makes its channels available; it does not automatically add every channel to a plot. For paired waveform files, open the `.wvf` and keep its matching `.hdr` beside it.

## Navigate and organize

Use the mouse wheel to zoom. Select **Pan** to move the view by dragging, or **Rectangle zoom** to select an area. **Zoom in**, **Zoom out** and **Fit both axes** provide toolbar alternatives. Plots in a tab synchronize their horizontal ranges.

**Add plot** creates another subplot in the current tab. Drag the dividers to change plot heights or sidebar widths. **New analysis** creates an independent time-domain tab. Double-click a tab label to rename it. The explorer stays available when switching tabs.

Right-click a signal in a plot's sidebar to change its color or assign its Y axis. Signals may use the main axis, share an additional axis, or use separate axes. Axis assignment changes display scaling, not the stored values or units. Right-click empty plot space for additional color options.

## Measure with differential cursors

Enable **Diff cursors** and move cursor A and B. All plots in that tab use the same horizontal cursor positions. The readout shows their positions, separation and per-signal amplitude differences. For time plots it also shows `1 / |Δt|` when the separation is nonzero.

Amplitudes are linearly interpolated between source samples. A cursor outside a channel's recorded range produces an unavailable value shown as NaN. A channel with a different time range can therefore show NaN while other channels still have valid values. Cursors are a readout tool; they do not add samples to the recording.

Select a channel and click **Statistics** for minimum, maximum, peak-to-peak, mean, RMS and population standard deviation. Enabled cursors select the analysis interval; otherwise the full signal is used. Nonfinite values are excluded from statistics.

## Analyze a spectrum

Select `Channel1` and click **FFT**. A frequency-domain tab opens with the selected signal. Drag additional source channels into its plots to calculate more spectra. FFT requires at least four finite real samples on a uniformly spaced time axis.

The calculation removes the mean and applies a Hann window. The vertical axis shows one-sided peak amplitude in the source unit. It is neither RMS amplitude nor power spectral density. The example's first channel has a 10 kHz sine component; the largest FFT bin will be near that frequency.

**Log X** and **Log Y** are enabled by default in FFT plots. Disable them to use linear axes. Logarithmic axes hide nonpositive coordinates, including the zero-frequency bin. Log Y does not convert amplitudes to decibels.

If time cursors were enabled when you opened FFT, their time interval becomes the FFT input interval. Use the FFT tab's **Time interval** fields and **Recalculate** to change it. The cursors inside the FFT plot measure **Hz and amplitude**, not source time. Changing frequency cursors does not change which time samples enter the FFT. Cursor amplitudes interpolate between FFT bins; this does not improve frequency resolution.

## Remove views or unload data

| Action | Effect |
| --- | --- |
| Select sidebar signals and press **Delete** | Removes those curves from that plot |
| **Clear plot** | Removes all curves from that subplot |
| **×** in a plot header | Removes the subplot |
| **Clear plots** toolbar action | Clears curves in the active tab's plots |
| Close an analysis tab | Removes that tab's views |
| Select a file in the explorer and press **Delete** | Unloads the file and removes its curves from every tab |

These actions do not delete measurement files on disk. There is currently no saved-workspace feature; tab layouts and display choices last for the running session.

## Export and command-line use

**Export all** exports all loaded source signals, including channels not currently plotted. It does not export just the active plot, spectra or a screenshot. Select an output format in the save dialog. MAT export preserves individual channel time vectors using OpenCaliper's interchange layout, described in the [MAT guide](MAT_FORMAT.md#opencaliper-mat-exports).

RAW and WVF export require real signals on identical uniform time axes. RAW accepts finite voltage/current data and starts the exported time axis at zero. WVF uses integer quantization. Conversion does not preserve all acquisition-specific metadata.

After activating the environment, the same operations are available without the GUI:

```bash
python -m opencaliper info examples/example.mat
python -m opencaliper stats examples/example.mat --signal 0
python -m opencaliper fft examples/example.mat spectrum.csv --signal 0
python -m opencaliper convert examples/example.mat output.raw
```

The channel index is zero-based and is printed by `info`. Existing outputs are refused by default. Conversion supports `--overwrite`; FFT CSV output requires a new filename. Command-line `--start` and `--stop` select source time bounds in seconds for FFT and statistics.

## If something does not work

- **No trace:** expand the file, add a channel, then fit both axes. On log axes, check that the relevant coordinates are positive.
- **MAT layout rejected:** compare field names, array lengths, dtypes and timing metadata with [the documented convention](MAT_FORMAT.md) and `examples/example.py`.
- **FFT rejected:** check the selected interval has enough samples, finite real amplitudes and uniform timestamps. The program does not automatically resample data.
- **Large file feels slow:** recordings are loaded into memory. FFT and export currently run on the GUI thread and can temporarily block interaction.
- **Window will not close during loading:** wait for current imports to finish. Import cancellation is not implemented.
- **Need to report a bug:** include the command or GUI steps, error text, operating system and Python version. Reproduce it with synthetic data where possible. Keep private recordings in `measFiles/` and out of public reports.

## Further reading

Use the [documentation index](README.md) to find all guides. For file conversion, start with the [MAT convention](MAT_FORMAT.md). To understand the implementation, read the [architecture overview](ARCHITECTURE.md) and [developer guide](DEVELOPMENT.md). The optional [Doxygen reference](DOXYGEN.md) adds browsable APIs and architecture drawings; you do not need its tools to run the viewer.


## Workspace and signal tools

### Save and reopen your analysis

Use **Workspace → Save workspace** (`Ctrl+Shift+S`) to write an `.ocw` archive. **Open workspace** (`Ctrl+Shift+O`) replaces the current session; you can undo that replacement. Save your current work first if you need it later.

The archive embeds all loaded time axes and samples, including derived channels. It restores tabs, subplot layout, signal colors, shared/separate axes, logarithmic settings, view ranges, cursor positions and annotations without requiring the original measurement files. Saving large recordings can take time and disk space. Spectrogram windows are temporary and can be regenerated from their source channels.

### Signal math and calculus

Open **Signal tools → Signal math**. The dialog lists channel identifiers such as `CH0` and `CH1`, including their names and units. Use these identifiers in expressions:

```text
CH0 - CH1
CH0 * CH1
abs(CH0) / 2
integrate(CH0)
differentiate(CH0)
```

Supported functions are `abs`, `sqrt`, `sin`, `cos`, `integrate` and `differentiate`; arithmetic supports `+`, `-`, `*` and `/`, parentheses and numbers. Channels in an expression must have identical timestamps. Calculus additionally requires strictly increasing timestamps. Integration is cumulative trapezoidal integration starting at zero; differentiation uses the sample time axis. Enter the output name and unit yourself; automatic physical unit algebra and implicit resampling are not performed. The result appears as a new source and curve, preserving the inputs.

### Filter a signal

**Signal tools → Filter** creates a zero-phase low-pass, high-pass or notch-filtered channel. Choose a cutoff/notch frequency in Hz. Butterworth order controls low/high-pass steepness; notch Q controls notch width. The input must have finite real values on a uniform time axis, the frequency must be below Nyquist, and the recording must contain enough samples for forward/backward filter padding. Inspect boundary transients before interpreting results. Add the original channel to the same plot to compare.

### Align recordings

**Signal tools → Align recording** creates shifted copies of a selected channel or all channels in its source recording. A positive offset moves the source later in time. Choose:

- **Manual shift:** enter a time offset in seconds.
- **Cross-correlation:** choose a reference; the tool maximizes demeaned cross-correlation over the initial overlap. Inputs need uniform, matching sample rates and nonconstant overlapping data. Periodic signals can produce ambiguous alignment.
- **Rising edge:** align the first interpolated rising threshold crossing in each selected channel.

Alignment shifts timestamps; it does not resample or change amplitudes.

### Annotations and events

Position A and B, then choose **Signal tools → Annotate cursor interval** and enter a label. The annotation is placed on the first plot in the current tab. Equal cursor positions create a point marker. Annotations are included in workspaces and plot exports. Right-click empty plot space and choose **Clear annotations** to remove a plot's markers; undo can recover them.

**Detect events** finds rising/falling threshold crossings, peaks above a level, pulse boundaries (both crossing directions), or outliers whose distance from the mean exceeds the selected standard-deviation multiple. Peak separation is specified in samples. Crossing times are linearly interpolated. Events are marked on the first time plot and their timestamps appear in the readout, where they can be copied. Refine settings if more than 1,000 events are found; markers are capped to keep the interface responsive. Pulse markers show boundaries; pulse widths can be measured with cursors.

### Spectrograms

**Signal tools → Spectrogram** opens a time/frequency heatmap for the selected channel. Choose samples per segment and overlap fraction. Longer segments improve frequency resolution while reducing time resolution. Input requires finite real values and uniform timestamps. The heatmap uses a Hann window, removes each segment's mean and displays power spectral density in dB relative to one squared signal unit per Hz. The color bar controls the display range. Pan and zoom with the mouse.

### Export plots

Choose **Workspace → Export plot**, select the subplot number and save a `.png`, `.svg` or `.pdf`. Exports include the current plot view, legend, units, visible cursor markers and annotations. Enabled cursors add numeric positions and per-channel amplitude measurements below the plot. PNG output is 2,400 pixels wide with 300 DPI metadata; SVG and PDF retain vector drawing for curves and text.

### Undo and redo

Use **Edit → Undo/Redo** (`Ctrl+Z` and the platform redo shortcut) for up to 50 structural actions, including curve removal, source unload, tabs, plots, colors, axis assignments, log modes, processing results and annotations. Undo retains references to original sample arrays rather than copying them for every edit. An unloaded recording can therefore remain in memory until its undo history expires. Mouse panning, wheel zooming, cursor dragging, source selection and external exports are outside structural history. Imports must finish before undoing or opening a workspace.

### Large recordings

Plots already use automatic peak-preserving display downsampling and clip curves to the visible horizontal range. Numerical operations continue to use full-resolution samples.

For data larger than convenient RAM capacity, open a NumPy `.npy` array containing rows of samples: column zero is time in seconds and each following column is one real numeric channel. A float64 array avoids converting the time column. For example:

```python
import numpy as np

# Allocate an on-disk array; fill it incrementally from your acquisition reader.
array = np.lib.format.open_memmap('large.npy', mode='w+', dtype='float64',
                                shape=(10_000_000, 3))
# Fill every row: array[:, 0] = times; array[:, 1:] = channel_samples
# Use bounded slices when writing large acquisitions.
array.flush()
```

After filling every row, open `large.npy` through **Open files**. The source arrays retain memory-mapped backing, and the operating system brings file pages into memory as accessed. Validation, fitting and processing still scan samples; filtering, FFT, derived channels and workspace loading can allocate full arrays. Existing MAT/MDF and other format readers still load their data into memory. Keep mapped files available and unchanged while using them.
