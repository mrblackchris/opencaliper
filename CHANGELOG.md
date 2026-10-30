# Changelog

## 0.1.0 — Unreleased

### Viewer and analysis

- S Parameter analysis pages for Touchstone S2P/S4P, with dB/linear magnitude,
  wrapped/unwrapped phase, real/imaginary views and reference-aware Smith charts.
- Keysight Infiniium HDF5 waveform import with integer scaling and float passthrough.
- Complex network samples, reference impedances and view choices persist in native MAT/workspaces.

- Per-subplot trace visibility checkboxes and Space-key toggles, preserved in workspaces and undo history.
- Scientific notation for cursor labels, measurements and plot-export readouts.
- Generated OpenCaliper logo, packaged window/taskbar icon and optional Linux desktop launcher.

- Unified Spectrum analyses for both calculated FFTs and receiver spectra, with New Time Analysis/New Spectrum Analysis toolbar actions.
- Spectrum file drops add detector traces to the target subplot; ESRP imports accept peak and legacy pk fields.

- Desktop viewer with shared file/signal explorer and independent time, FFT and Spectrum tabs.
- Resizable linked plots, shared/separate Y axes, configurable colors and logarithmic scales.
- Plot-local signal renaming with context menus, workspace persistence and undo/redo.
- Differential cursors with interpolated values and alternating A/B left-click placement after zooming.
- Hann-windowed FFT, source intervals, frequency cursors and descriptive statistics.
- Explicit linear FFT resampling for uneven timestamps with Auto/manual Hz rates and retry support.
- Signal expressions, differentiation/integration, zero-phase filtering and recording alignment.
- Annotations, threshold/peak/pulse/outlier detection and interactive PSD spectrograms.
- PNG/SVG/PDF plot export with legends, units and cursor measurements.

### Files and sessions

- Optional MAT date/time metadata is read when recognized and silently defaults to the epoch when missing, malformed or ambiguous.

- Portable workspace archives containing source/derived channels and plot settings.
- Structural undo/redo and memory-mapped NPY input with cached, bounded-memory fit scans.
- Shared converter registry and separate per-format readers/exporters, with a native MAT dispatcher.
- ESRP MAT vectors (`freq`, `avg`, `pk`, `qpk`) open directly as measured spectra.
- Numeric MDF/MF4 state channels retain values when text labels are present.
- MAT, MDF/MF4, Keysight BIN, Yokogawa WVF/HDR and LTspice RAW support within documented limits.

### Startup, fixes and contributor support

- Single-file Windows PyInstaller build recipe, native Windows artifact workflow and packaged executable self-test.
- Embedded project/dependency notices with Help menu access.

- Bound Qt/Shiboken below 6.12 on Python versions below 3.12 to avoid a reproduced None-reference-count abort during plot use.
- CI reports dependency versions and lets Python matrix jobs finish independently.

- Managed `.venv` launchers, existing-environment launchers and root `run_opencaliper.py`.
- Shared GUI, command-line and Python interfaces for import, analysis and export.
- Modal processing dialogs keep controls alive until values have been read.
- Specific FFT input diagnostics and retry of channels that initially failed.
- Synthetic regression tests for numerical, format, workspace and real mouse/dialog behavior.
- User, CLI, Python API, workspace, architecture, development and converter guides.
- Doxygen API reference and synchronized Graphviz/Mermaid architecture drawings.
- CI test/package builds and downloadable HTML reference generation with warning checks.
