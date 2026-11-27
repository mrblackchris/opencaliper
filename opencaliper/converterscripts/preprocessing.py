"""Optional time-domain processing before converter MAT export.

Pipeline: selected zero-phase Butterworth filter, anti-alias low-pass, then
keep every Nth sample. Channels retain their names, units and time origin.
No processing is performed by default; original sample arrays are unchanged.
"""
import numpy as np
from scipy import signal as dsp
from ..core import Recording, Signal
from ..processing import uniform


def prepare(recording, downsample=1, filter_kind='none', cutoff=None, order=4):
    """Filter finite uniformly sampled real time signals and reduce sample counts.

    Downsampling always includes an eighth-order zero-phase anti-alias filter
    at 80 percent of the new Nyquist frequency. The optional user-selected
    low/high-pass is applied first. Forward/backward filtering has edge effects.
    Existing spectra/S-parameters are rejected when processing is requested.
    """
    if type(downsample) is not int or downsample < 1:
        raise ValueError('Downsample factor must be a positive integer')
    if filter_kind not in ('none', 'lowpass', 'highpass'):
        raise ValueError('Choose no filter, low-pass or high-pass')
    if type(order) is not int or not 1 <= order <= 20:
        raise ValueError('Filter order must be between 1 and 20')
    if downsample == 1 and filter_kind == 'none': return recording
    signals = []
    for source in recording.signals:
        try:
            fs = uniform(source)
            y = source.values
            if filter_kind != 'none':
                if cutoff is None or not np.isfinite(cutoff) or not 0 < cutoff < fs/2:
                    raise ValueError(f'Filter cutoff must be positive and below Nyquist ({fs/2:g} Hz)')
                if filter_kind == 'highpass' and cutoff >= fs/(2*downsample):
                    raise ValueError('High-pass cutoff must be below the output Nyquist frequency; reduce the downsample factor')
                sos = dsp.butter(order, cutoff, btype=filter_kind, fs=fs, output='sos')
                y = dsp.sosfiltfilt(sos, y)
            if downsample > 1:
                sos = dsp.butter(8, .8*(fs/(2*downsample)), fs=fs, output='sos')
                y = dsp.sosfiltfilt(sos, y)
            signals.append(Signal(source.name, source.time[::downsample],
                                  y[::downsample].copy(), source.unit,
                                  source.domain, source.reference_impedance))
        except ValueError as exc:
            raise ValueError(f'{source.name}: {exc}') from exc
    return Recording(signals, recording.source, recording.timestamp)
