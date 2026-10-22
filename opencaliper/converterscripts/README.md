# Converter scripts

All file-format adapters live here. The GUI, Python API and command-line tools
share the same dispatcher and registry. No Qt dependency is needed for conversion.

## Convert a measurement

From the project folder after installing OpenCaliper in your Python environment:

```bash
python -m opencaliper.converterscripts recording.mf4
python -m opencaliper.converterscripts capture.wvf capture.mat
python opencaliper/converterscripts/convert.py simulation.raw simulation.mat
```

Without an output argument, `recording.mf4` becomes
`recording.opencaliper.mat`. Input files remain unchanged. An existing output is
refused unless `--overwrite` is supplied. Input and output must be different files.
The same dispatcher also supports exports:

```bash
python -m opencaliper.converterscripts capture.mat capture.mf4
python -m opencaliper.converterscripts capture.mat capture.wvf
opencaliper convert capture.mdf capture.mat
```

Format detection uses the **case-insensitive filename extension**; each reader
validates its supported contents. Rename a misleading extension before conversion.
WVF input requires its `.hdr`/`.HDR` companion beside it; WVF export creates both.
There is no automatic resampling. RAW/WVF writers require real samples with
identical uniform time axes, and WVF quantizes to int16. RAW requires finite
voltage/current data and starts time at zero while recording the original origin
in its header. These conversions do not preserve every device-specific field.

## Files and responsibilities

| File | Function |
| --- | --- |
| `convert.py` | `detect_format`, `load`, `export`, `convert_file`, terminal entry point |
| `formats.py` | Registry mapping extensions to reader/exporter modules; GUI filters |
| `matconvert.py` | `read(path)`: acquisition and native OpenCaliper MAT |
| `esrpconvert.py` | ESRP receiver `freq`/`avg`/`pk`/`qpk` MAT spectra; selected by `matconvert.py` from contents |
| `mdfconvert.py` | `read(path)`: MDF/MF4 numeric scalar channels |
| `wvfconvert.py` | `read(path)`: Yokogawa single-block IS2 WVF/HDR |
| `rawconvert.py` | `read(path)`: LTspice single-plot transient RAW |
| `binconvert.py` | `read(path)`: Keysight AG normal/average float32 waveforms |
| `npyconvert.py` | `read(path)`: memory-mapped time/channel columns |
| `matexport.py` | `write(recording, path, overwrite=False)`: native MAT |
| `mdfexport.py` | `write(...)`: MDF 3.30 and MDF 4.10 |
| `wvfexport.py` | `write(...)`: WVF plus HDR |
| `rawexport.py` | `write(...)`: LTspice transient RAW |
| `_waveform.py` | Shared real/uniform-axis validation for RAW/WVF export |

MDF 3 and MDF 4 share adapters because the asammdf library handles both. Optional
format-specific libraries are imported inside adapters, not by the registry.
Existing `opencaliper.load()` and `opencaliper.export()` remain supported and route
through `convert.py`.

## Expected in-memory format

The viewer consumes **`Recording` containing `Signal` objects**, defined in
[`../core.py`](../core.py). A reader's `read(path)` must return this model, with
physical amplitudes, not raw ADC counts. Set `Signal.domain="time"` (default)
for timestamps in **seconds**, or `domain="frequency"` for frequency bins in **Hz**.
The compatible `time` array field holds horizontal coordinates in either domain:

```python
from opencaliper.core import Recording, Signal

recording = Recording(
    signals=[Signal(name='Voltage', time=[0.0, 0.001, 0.002],
                    values=[1.2, 1.5, 1.3], unit='V')],
    source=str(path),
)
```

- Each channel has nonempty, equally sized, one-dimensional numeric arrays.
- The horizontal axis must be finite and nondecreasing. Independent channel time axes are valid.
- Values may be real or complex and may include NaN/Inf. Individual analyses and
  exporters impose stricter constraints. Use NaN for unavailable samples where
  the source format supports that interpretation.
- Apply acquisition gain/offset exactly once. Preserve units and names. Do not
  silently sort timestamps, interpolate, align or resample channels.
- Set `source` to the input path. Preserve the acquisition `datetime` in
  `Recording.timestamp` when present; its default is the Unix epoch when unknown.
- Reject malformed/unsupported inputs with descriptive `ValueError` messages;
  allow I/O errors to propagate. Do not turn a parsing failure into an empty file.
- Do not import or manipulate GUI widgets in adapters.

## Native disk format (OpenCaliper MAT)

The default conversion output is a MATLAB `.mat` file written by `matexport.py`.
It preserves independent channel time axes and uses these top-level fields:

| Field | Type / meaning |
| --- | --- |
| `recording_timestamp` | ISO 8601 acquisition datetime string |
| `signal_0_name` | Channel name string |
| `signal_0_unit` | Unit string, e.g. `V` |
| `signal_0_time` | Numeric vector: seconds for time data, Hz for frequency data |
| `signal_0_domain` | `time` (default when absent) or `frequency` |
| `signal_0_values` | Matching numeric vector of physical amplitudes |

Repeat `signal_N_*` for zero-based integer channel indices. Row and column vectors
are accepted and flattened. Channels are loaded in numeric index order.
`recording_timestamp` is optional on import; if absent it defaults to the epoch.
Frequency-domain channels are exported only to native MAT; time-only writers reject them. ESRP MAT spectra are detected from `freq` and detector fields and routed through `esrpconvert.py`.
The legacy `ChannelN_t1` acquisition MAT layout is also supported; see the
[MAT guide](../../docs/MAT_FORMAT.md). Workspaces (`.ocw`) additionally store plot
state; they are not the converter interchange format.

## Add another format

1. Create `fooconvert.py` in this folder. Implement `read(path)` returning the
   documented model. Keep the external reader dependency inside the function:

   ```python
   # opencaliper/converterscripts/fooconvert.py
   from pathlib import Path
   from ..core import Recording, Signal

   def read(path):
       """Decode Foo measurements to physical values and seconds."""
       from foo_library import read_file
       path = Path(path)
       data = read_file(path)
       return Recording([
           Signal(channel.name, channel.seconds, channel.physical_values,
                  channel.unit)
           for channel in data.channels
       ], source=str(path), timestamp=data.timestamp)
   ```

2. Add one entry to `FORMATS` in `formats.py`:

   ```python
   '.foo': Format('Foo measurement', 'fooconvert'),
   ```

3. Optionally create `fooexport.py` with
   `write(recording, path, overwrite=False)` and register:

   ```python
   '.foo': Format('Foo measurement', 'fooconvert', 'fooexport'),
   ```

   Use `None` for the reader for an export-only format. The dispatcher checks
   existing destinations and rejects empty recordings before calling writers.
   Writers must still honor `overwrite` when opening files, including companion
   files, and validate format restrictions before writing where possible. The
   writer's return value is ignored; the dispatcher returns the requested path.

4. Add dependency metadata in `pyproject.toml` if needed, synthetic tests for
   scaling/timing/units and malformed files, and an independently verified export
   test. Registering the extension automatically updates the GUI file pickers;
   no changes to `core.py`, `gui.py` or `cli.py` are needed. Modules added to this
   package are included in source and wheel distributions.

Run checks with `python -m unittest discover -s tests -v`. A round trip alone
cannot prove correct scaling: reader and writer can share the same mistake.
