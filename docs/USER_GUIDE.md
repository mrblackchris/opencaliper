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
