# Converter window and custom scripts

Click **Converter** in the main toolbar. This opens a separate window for
preparing compatible MAT files without first loading the inputs into plots.

1. Click **Add files…** or drop local files into the list. Any extension is allowed.
2. Choose **Automatic format detection**, a built-in converter, or
   **Choose .py script…** for your own reader. One selected converter applies to
   the list; Automatic can mix registered formats.
3. Choose an output folder, or leave it blank to save beside each input.
4. Click **Convert to MAT**. Each row reports success or its own error; one
   failed input does not prevent the other files from converting.
5. Click **Load converted files** to import successful outputs into the viewer.
   Frequency measurements open directly in Spectrum.

Outputs are named `input.opencaliper.mat`. Existing outputs are refused unless
**Replace existing output files** is checked. Selected inputs are protected from
replacement, and duplicate output names are rejected before conversion starts.
Conversion runs in a worker thread. **Cancel conversion** finishes the current
file and cancels remaining files. Finish or cancel before closing the window or
application. Successful files remain available to load after a partial failure
or cancellation.

## Filtering and downsampling

Set **Downsample factor** to N to keep every Nth time sample, reducing the sample
rate by N. The default 1 preserves all samples. Before reducing the samples,
the converter always applies an eighth-order zero-phase Butterworth anti-alias
low-pass at 80% of the new Nyquist frequency.

Use **Filter before downsampling** to additionally apply a low-pass or high-pass
Butterworth filter, specifying its cutoff in Hz and order (1–20). This filter
runs before the anti-alias filter and sample reduction. Factor 1 also allows
filtering without downsampling. High-pass filtering alone does not prevent
aliasing. A high-pass cutoff must be below the output Nyquist frequency.

Processing requires finite real time signals with uniform, strictly increasing
timestamps and enough samples for forward/backward filter padding. Irregular
time axes, short records, spectra and S-parameters produce a per-file error
when processing is requested; they still convert normally with processing off.
Filters have edge transients and change amplitudes near their cutoffs. Names,
units and original input files are preserved. Shared-time alignment, if enabled,
runs after filtering/downsampling. Its optional interpolation does not add an
anti-alias filter: use the downsample factor for bandwidth-controlled reduction.

## Large exports

There is no one-million-point limit on MAT export. Regression tests export and
reload 1,100,001 samples with both layouts and with compression on or off.
**Compress MAT output** produces smaller files; disable it for faster large
exports and reduced compression-buffer memory. Disabling compression does not
discard samples. Available memory, disk space and the classic MAT format's
per-variable size restrictions still apply. A separate 100-million-point guard
applies only when generating a shared resampling grid, not to ordinary export.
For example, 10 seconds at 200 ns per sample contains about 50 million samples
and is within this limit. Each float64 axis or amplitude vector uses about
400 MB at that size; processing and writing need additional memory. If channels
already share an identical uniform axis, leave shared resampling unchecked to
avoid unnecessary interpolation. Downsampling reduces the exported point count.
Conversion runs off the GUI thread; compression can take time on long records.

## Compatible paired MAT output

The **MAT layout** selector offers the original separate-axis layout described
below and **One shared uniform time vector (t1)**. Shared-time output contains:

```text
t1              one common time vector in seconds
Signal1_t1      first signal's amplitude samples
Signal2_t1      second signal's amplitude samples
```

Names and units remain in `SignalN_name` and `SignalN_unit`. The viewer reads
this layout directly. With resampling unchecked, every channel must already
have the same uniformly spaced time coordinates; mismatches produce an error.
Frequency channels require the separate-axis layout.

To align uneven or independent time axes, explicitly check **Resample/align onto
a shared uniform time grid** and select a rate in Hz. Auto uses the slowest median
source rate. Conversion linearly interpolates within the channels' common time
interval only, without extrapolating. This trims non-overlapping portions. No
anti-alias filter is applied, and upsampling does not add measured bandwidth.
Duplicate timestamps, nonfinite samples, no overlap, or a grid over 100 million
samples produce errors. Inputs remain unchanged. Leave this option unchecked
to preserve the original samples exactly.

With separate axes selected, the Converter window writes numbered pairs:

```text
Signal1_u       amplitudes
Signal1_t       time in seconds
Signal1_name    original signal name
Signal1_unit    amplitude unit

Signal2_u       amplitudes
Signal2_f       frequency in Hz
Signal2_name    original signal name
Signal2_unit    amplitude unit
```

Numbered MATLAB-safe field names allow original names containing spaces, dots
or parentheses to survive in `_name` metadata. With processing and shared-time
alignment disabled, arrays are not resampled or quantized. Complex values and missing amplitudes are retained. Optional
`SignalN_domain` and `SignalN_reference_impedance` preserve S-parameter identity
and reference resistance; ordinary `_u`/`_t` or `_u`/`_f` pairs without these
fields also load. Acquisition time is stored as `recording_timestamp`.

The regular **Export all** and existing CLI export formats retain their existing
layout. The Converter window's paired output is an additional interchange path.

## Write your own converter

Click **Create converter template…**, choose a new `.py` filename, and edit its
`read(path)` function. A reader receives a `pathlib.Path` and returns the shared
`Recording` model. It does not need Qt or MAT-writing code:

```python
from pathlib import Path
import numpy as np
from opencaliper import Recording, Signal

CONVERTER_NAME = 'My instrument'

def read(path):
    path = Path(path)
    data = np.loadtxt(path, delimiter=';', skiprows=2)
    signal = Signal('Voltage', data[:, 0], data[:, 1], 'V', domain='time')
    return Recording([signal], source=str(path))
```

For frequency measurements use `domain='frequency'`, with coordinates in Hz.
Return multiple `Signal` objects for multiple channels. Each needs nonempty,
matching numeric vectors and a finite nondecreasing horizontal axis. Use physical
values, apply gain/offset once, retain units, and raise a descriptive exception
for unsupported input. Missing acquisition dates can use Recording's default.

Save scripts in `opencaliper/converterscripts/` in a source checkout, then click
**Refresh**. Scripts defining `read(path)` appear automatically; optional constant
`CONVERTER_NAME` provides their display name. Alternatively, choose any script
directly or select another directory with **Converter scripts folder…**.
No registry edit is needed for manually selected scripts. For automatic extension
detection and normal file-picker integration, also add a reader to `formats.py`.

Discovery inspects Python syntax without executing scripts. Selecting **Convert**
executes the chosen script with the application's Python environment and
permissions; choose scripts you trust. Each conversion reads the current source,
so edits take effect on the next run. Use `opencaliper` imports and installed
libraries; the reader is given a Path, so it should not rely on a working directory.

### Standalone executable

Built-in converters remain available inside the executable. For your own files,
create a `converterscripts` directory beside the executable, select another
directory, or browse directly to a `.py` script. The template is bundled and can
be copied from the Converter window. Custom scripts can use Python and libraries
already bundled with the executable. Additional dependencies require a rebuilt
executable; when running from source, install them in the selected environment.

### Python API

```python
from pathlib import Path
from opencaliper.converterscripts.conversion import Converter, convert_one

reader = Converter('My instrument', script=Path('my_converter.py'))
convert_one('recording.custom', 'recording.opencaliper.mat', reader)
```

`convert_one` also accepts built-in module selections and Automatic by default.
`pairedexport.write(recording, path)` writes paired MAT from an existing Recording.
Parsing and MAT serialization finish before a prior output is replaced.

## Supplied EMC receiver CSV

The local `RE02 bico 30MHz-250MHz BW 120 kHz vertical.csv` has a column-name row,
a unit row and 7,335 data rows. The EMC converter reads **QPK Level**, **PK+ Level**
and **AVG Level** as Quasipeak, Peak and Average. It converts MHz to Hz and retains
dBµV/m amplitudes. Polarization, comments, range, antenna height and correction
columns are metadata, not plotted signals. Correction is not applied a second
time. Repeated/non-increasing sweeps must be separated before import.

Automatic CSV detection recognizes this schema; it is also available explicitly
as **EMC receiver CSV (QPK / PK+ / AVG)**. Tests use synthetic fixtures plus the
local example when present. Local measurement files remain ignored by Git.

Implementation: [converter_gui.py](../opencaliper/converter_gui.py),
[conversion.py](../opencaliper/converterscripts/conversion.py),
[pairedexport.py](../opencaliper/converterscripts/pairedexport.py), and
[converter_template.py](../opencaliper/converterscripts/converter_template.py).
