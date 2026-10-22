# Python API

OpenCaliper's numerical and conversion APIs run without creating a Qt application.
Install dependencies in the interpreter running your code. The source definitions
and [Doxygen reference](DOXYGEN.md) complement this guide.

## Model and file I/O

```python
import numpy as np
from opencaliper import Signal, Recording, load, export

t = np.arange(1024) / 1024
voltage = Signal('Voltage', t, 3 * np.sin(2 * np.pi * 64 * t), 'V')
recording = Recording([voltage])
export(recording, 'generated.mat')  # Refuses an existing destination.
restored = load('generated.mat')
```

`Signal(name, time, values, unit='', domain='time')` validates nonempty numeric
arrays, matching lengths and a finite nondecreasing horizontal axis. Arrays are
flattened. `domain='time'` means seconds; `domain='frequency'` means Hz. The field
name `time` is retained for API compatibility in both domains. Complex and
nonfinite amplitudes are accepted by the model; operations apply their own limits.

`Recording(signals, source='', timestamp=...)` groups channels, each of which may
have a different horizontal axis. Unknown acquisition time defaults to the Unix
epoch. Imported values are physical amplitudes, not raw ADC counts. Treat source
arrays as read-only even though Python does not enforce immutability.

`load(path)` returns a recording using the shared converter registry.
`export(recording, path, overwrite=False)` returns the output `Path`; output
constraints depend on the format. Native MAT retains frequency/time domain
metadata. `convert_file(input, output=None, overwrite=False)` in
`opencaliper.converterscripts.convert` defaults to `input.opencaliper.mat`.
The [adapter guide](../opencaliper/converterscripts/README.md) documents format I/O.

For an already measured spectrum:

```python
spectrum = Signal('Peak', [1e6, 2e6, 3e6], [-45, -40, -50],
                  'dBm', domain='frequency')
export(Recording([spectrum]), 'measured-spectrum.mat')
```

Do not run FFT on this channel. Loading an ESRP MAT file creates such signals and
the GUI opens a Spectrum tab automatically.

## Statistics, intervals and cursors

```python
from opencaliper.analysis import statistics, cursor_values

print(statistics(voltage, start=0.1, stop=0.5))
print(cursor_values(voltage, 0.1, 0.2))
```

`Signal.region(start=None, stop=None)` returns array slices between inclusive
bounds, sorts two reversed bounds and does not add boundary samples. Statistics
use these samples, skip nonfinite values, and use magnitudes for complex input.
Standard deviation uses `ddof=0`. No finite samples is an error.

`cursor_values(signal, a, b)` linearly interpolates real amplitudes and returns
`a`, `b`, `delta`, `dt` and `frequency`. `dt` is the horizontal difference; its
unit is seconds or Hz according to the channel. `frequency = 1/abs(dt)` is useful
only for time-domain data and is `None` at zero separation. Values beyond the
recorded range are NaN. Spectrum interpolation is between measured frequency
points, not an improvement to spectral resolution.

## FFT and irregular acquisition times

```python
from opencaliper.analysis import fft

frequency, amplitude = fft(voltage, start=0.1, stop=0.8)
# Explicit interpolation for an irregular time-domain recording:
frequency, amplitude = fft(voltage, resample=True, sample_rate=1024)
```

`fft(signal, start=None, stop=None, *, resample=False, sample_rate=None)` requires
at least four finite real time-domain samples and strictly increasing timestamps.
Without resampling, spacing must be approximately uniform. It removes the mean,
applies a Hann window, and returns one-sided peak amplitudes in the input unit.
DC and even-length Nyquist bins are not doubled. This is not PSD or a dB spectrum.

`resample=True` uses linear interpolation on a uniform grid within the selected
source range. A positive finite `sample_rate` specifies Hz; `None` means reciprocal
median source interval. A rate without `resample=True` is rejected. Resampling
does not modify the source, fill NaN/Inf values, or resolve repeated timestamps.
Generated grids are limited to 10 million samples and must have at least four
samples. Interpolation can attenuate high frequencies and bridge gaps; it adds no
measured bandwidth and is not an anti-alias filter for downsampling.

## Signal processing

```python
from opencaliper.processing import expression, filtered, aligned, events, spectrogram

half = expression('CH0 / 2', {'CH0': voltage}, name='Half voltage', unit='V')
low = filtered(voltage, kind='lowpass', frequency=100, order=4)
reference = Signal('Reference', t, 3 * np.sin(2 * np.pi * 64 * t), 'V')
shifted = aligned(voltage, reference)
crossings = events(voltage, kind='rising', threshold=0)
times, frequencies, psd_db = spectrogram(voltage, segment=256, overlap=0.5)
```

| Function | Contract |
| --- | --- |
| `uniform(signal)` | Validate at least four finite real, uniformly spaced time samples; return Hz |
| `expression(text, signals, name='Math', unit='')` | Arithmetic and approved functions; shared exact axis and domain; return a new Signal |
| `filtered(source, kind, frequency, order=4, quality=30)` | Uniform finite real time samples; zero-phase lowpass/highpass Butterworth or notch; return a new Signal |
| `aligned(source, reference)` | Matching uniform sample rates and nonconstant overlap; return a timestamp-shifted copy maximizing demeaned cross-correlation |
| `events(source, kind, threshold, distance=1)` | Finite real time data; return event times for rising/falling crossings, peaks, pulses or outliers |
| `spectrogram(source, segment=256, overlap=0.5)` | Uniform finite real time data; return segment times, Hz bins and PSD dB matrix |

Expression syntax supports numbers, parentheses, `+ - * /`, unary signs and
`abs`, `sqrt`, `sin`, `cos`, `differentiate`, `integrate`. It does not execute Python
code. Calculus requires strictly increasing time-domain data; differentiation
uses the sample axis and integration uses cumulative trapezoids starting at zero.
Output units are supplied by the caller; there is no automatic unit algebra.

Filters need a cutoff/notch strictly below Nyquist and enough samples for padding.
`quality` applies to the notch, `order` to Butterworth filters. Boundary transients
can affect interpretation. Alignment changes timestamps, not values; periodic
signals may have ambiguous correlation peaks. Manual and rising-edge alignment
are offered through the GUI using shifted copies of the same model.

Crossing times are linearly interpolated. `pulses` returns both rising and falling
boundaries. Peaks use height `threshold` and minimum sample separation `distance`.
Outlier threshold is a positive multiple of population standard deviation around
the mean. The GUI limits markers to 1,000; the numerical API returns all matches.

Spectrograms use a Hann window, per-segment mean removal and PSD scaling. Rows of
`psd_db` correspond to frequency, columns to segment time. Values are dB relative
to one squared source unit per Hz. Segment length must fit the recording and be
at least four; overlap must satisfy `0 <= overlap < 1`.

## GUI state APIs

`opencaliper.gui.run(files=())` starts the application. `Window` exposes interactive
commands, with `WorkspaceMixin` and `ToolsMixin` handling persistence and tools.
These require QApplication and execution on the GUI thread. Use numerical APIs
for scripts instead of controlling widgets. See [Architecture](ARCHITECTURE.md)
and [Workspace format](WORKSPACE_FORMAT.md) before changing persistence or undo.
