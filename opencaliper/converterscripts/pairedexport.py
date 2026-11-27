"""Portable SignalN_u / SignalN_t or SignalN_f MAT conversion output."""
from pathlib import Path
import os
import tempfile
import numpy as np
from scipy.io import savemat


MAX_SHARED_SAMPLES = 100_000_000


def shared_sample_count(start, stop, rate):
    """Validate a shared grid before allocating up to 100 million samples."""
    points = (stop-start)*rate
    if stop <= start or points < 1:
        raise ValueError('Signals need an overlapping interval containing at least two output samples')
    if not np.isfinite(points) or points >= MAX_SHARED_SAMPLES:
        raise ValueError('Shared-time resampling exceeds 100 million samples; reduce the rate or downsample first')
    return int(np.floor(points+1e-8))+1


def resample_shared(recording, sample_rate=None):
    """Interpolate time channels onto a uniform grid over their common interval.

    Auto uses the slowest median source interval. No extrapolation or anti-alias
    filtering is performed. Source arrays are unchanged; nonfinite values and
    duplicate timestamps require repair before interpolation.
    """
    from ..core import Recording, Signal
    if any(s.domain != 'time' for s in recording.signals): raise ValueError('Shared t1 resampling requires time signals')
    intervals = []
    for s in recording.signals:
        dt = np.diff(s.time)
        if not len(dt) or np.any(dt <= 0) or not np.isfinite(s.values).all():
            raise ValueError(f'{s.name}: resampling needs at least two finite samples and strictly increasing timestamps')
        intervals.append(float(np.median(dt, overwrite_input=True)))
        del dt
    rate = 1/max(intervals) if not sample_rate else float(sample_rate)
    if not np.isfinite(rate) or rate <= 0: raise ValueError('Shared-time sample rate must be finite and positive')
    start = max(s.time[0] for s in recording.signals); stop = min(s.time[-1] for s in recording.signals)
    count = shared_sample_count(start, stop, rate)
    # Build in place to avoid multiple full-size temporary vectors on long records.
    axis = np.arange(count, dtype=float)
    axis /= rate
    axis += start
    if axis[-1] > stop: axis = axis[:-1]
    if len(axis) < 2 or np.any(np.diff(axis) <= 0): raise ValueError('Sample rate cannot form a strictly increasing shared time grid')
    return Recording([Signal(s.name, axis, np.interp(axis, s.time, s.values), s.unit) for s in recording.signals],
                     recording.source, recording.timestamp)


def write(recording, path, overwrite=False, axis_mode='per_signal', resample=False, sample_rate=None, compress=True):
    """Write independent channels with safe MATLAB identifiers and original names.

    Extra domain/reference metadata retains S-parameter semantics. The paired
    reader also accepts ordinary pairs without those optional metadata fields.
    """
    from ..core import Recording, Signal
    if not isinstance(recording, Recording) or not recording.signals:
        raise ValueError('Converter must return a nonempty Recording of Signal objects')
    path = Path(path)
    if path.suffix.lower() != '.mat': raise ValueError('Paired output must use a .mat extension')
    if path.exists() and not overwrite: raise FileExistsError(path)
    if axis_mode not in ('per_signal', 'shared_time'): raise ValueError('Unknown MAT axis layout')
    if resample and axis_mode != 'shared_time': raise ValueError('Resampling is available only with shared t1 output')
    if resample: recording = resample_shared(recording, sample_rate)
    data = {'recording_timestamp': recording.timestamp.isoformat()}
    common = None
    for i, signal in enumerate(recording.signals, 1):
        if not isinstance(signal, Signal): raise TypeError('Recording.signals must contain Signal objects')
        # Validate mutable models again at the extension boundary.
        checked = Signal(signal.name, signal.time, signal.values, signal.unit,
                         signal.domain, signal.reference_impedance)
        if checked.domain != 'time' and (checked.time < 0).any():
            raise ValueError(f'{checked.name}: frequency coordinates must be nonnegative')
        key = f'Signal{i}'
        if axis_mode == 'shared_time':
            if checked.domain != 'time': raise ValueError('Shared t1 export requires time signals; use per-signal axes for frequency data')
            if common is None:
                common = checked.time
                dt = np.diff(common)
                if len(dt) and (np.any(dt <= 0) or not np.allclose(dt, dt[0], rtol=1e-4, atol=abs(dt[0])*1e-8)):
                    raise ValueError('Shared t1 export requires uniform timestamps; use per-signal axes or enable shared-time resampling')
                data['t1'] = common
            elif not np.array_equal(checked.time, common):
                raise ValueError('Shared t1 export requires identical time vectors for all signals; use per-signal axes or enable shared-time resampling')
            data[key+'_t1'] = checked.values
        else:
            data[key+'_u'] = checked.values
            data[key+('_t' if checked.domain == 'time' else '_f')] = checked.time
        data[key+'_name'] = checked.name; data[key+'_unit'] = checked.unit
        data[key+'_domain'] = checked.domain
        if checked.reference_impedance is not None: data[key+'_reference_impedance'] = checked.reference_impedance
    temp = None; reserved = False
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.mat', delete=False) as file:
            temp = Path(file.name); savemat(file.file, data, do_compression=compress)
        if not overwrite:
            # Reserve the name without overwriting another process's output.
            with path.open('xb'): pass
            reserved = True
        os.replace(temp, path); temp = None; reserved = False
    finally:
        if temp is not None: temp.unlink(missing_ok=True)
        if reserved: path.unlink(missing_ok=True)
    return path
