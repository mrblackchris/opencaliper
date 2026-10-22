"""ESRP receiver MAT spectra: freq (Hz), avg/pk/qpk detector amplitude vectors.

Values are already spectra and must never be transformed with an FFT. Optional
unit/avg_unit/pk_unit/qpk_unit fields label amplitudes without changing values.
An optional freq_unit (Hz/kHz/MHz/GHz) scales frequencies to Hz; absent means Hz.
"""
from pathlib import Path
import numpy as np
from ..core import Recording, Signal
from ..acquisition import load_mat, text_value


DETECTORS = {'avg': 'Average', 'pk': 'Peak', 'qpk': 'Quasipeak'}


def read_data(data, path):
    """Decode already-loaded MAT variables; reject matrices and mismatched vectors."""
    def vector(key):
        array = np.asarray(data[key])
        if array.dtype.kind not in 'biuf' or array.squeeze().ndim > 1 or array.size == 0:
            raise ValueError(f'ESRP {key} must be a nonempty real numeric vector')
        return array.reshape(-1)
    frequency = vector('freq').astype(float)
    unit = text_value(data['freq_unit']).strip().lower() if 'freq_unit' in data else 'hz'
    factors = {'hz': 1., 'khz': 1e3, 'mhz': 1e6, 'ghz': 1e9}
    if unit not in factors: raise ValueError(f'Unsupported ESRP frequency unit: {unit}')
    frequency = frequency*factors[unit]
    if not np.isfinite(frequency).all() or np.any(frequency < 0) or np.any(np.diff(frequency) <= 0):
        raise ValueError('ESRP freq must contain finite, nonnegative, strictly increasing frequencies')
    signals = []
    for key,name in DETECTORS.items():
        if key not in data: continue
        values = vector(key)
        if len(values) != len(frequency): raise ValueError(f'ESRP {key} length does not match freq')
        amplitude_unit = data.get(key+'_unit', data.get('unit'))
        signals.append(Signal(name, frequency, values,
                              text_value(amplitude_unit) if amplitude_unit is not None else '',
                              domain='frequency'))
    if not signals: raise ValueError('ESRP MAT needs at least one detector vector: avg, pk or qpk')
    return Recording(signals, str(path))


def read(path):
    """Read an ESRP MAT file to frequency-domain OpenCaliper signals."""
    return read_data(load_mat(Path(path)), path)
