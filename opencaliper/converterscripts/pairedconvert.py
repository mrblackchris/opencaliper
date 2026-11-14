"""Named vector pairs: PREFIX_u amplitudes and PREFIX_t seconds/PREFIX_f Hz.

Arrays must be numeric row/column vectors with matching lengths. Optional
PREFIX_unit and PREFIX_name describe Y values. PREFIX_t_unit/PREFIX_f_unit can
specify an axis unit; defaults are seconds/Hz. Complex amplitudes are retained.
"""
import re
import numpy as np
from ..core import Signal, Recording
from ..acquisition import text_value, timestamp


AXIS_UNITS = {
    'time': {'s': 1., 'second': 1., 'seconds': 1., 'ms': 1e-3,
             'us': 1e-6, 'µs': 1e-6, 'μs': 1e-6, 'ns': 1e-9, 'ps': 1e-12},
    'frequency': {'hz': 1., 'khz': 1e3, 'mhz': 1e6, 'ghz': 1e9, 'thz': 1e12},
}


def axis_scale(unit, domain):
    """Convert a declared time/frequency unit to seconds/Hz; reject unknown units."""
    if not unit: return 1.
    try: return AXIS_UNITS[domain][unit.strip().lower()]
    except KeyError as exc: raise ValueError(f'Unsupported {domain} axis unit: {unit}') from exc


def vector(value, name, real=False):
    """Validate vector shape before flattening, without losing complex Y samples."""
    value = np.asarray(value)
    if (value.dtype.kind not in 'biufc' or value.ndim > 2 or
            (value.ndim == 2 and min(value.shape) > 1) or not value.size):
        raise ValueError(f'{name}: expected a nonempty numeric row or column vector')
    if real and np.iscomplexobj(value):
        if np.any(value.imag != 0): raise ValueError(f'{name}: horizontal coordinates must be real')
        value = value.real
    return value.reshape(-1)


def prefixes(data):
    """Find amplitude prefixes in natural numeric order (Signal2 before Signal10)."""
    def natural(name): return [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', name)]
    return sorted((key[:-2] for key in data if key.endswith('_u') and not key.startswith('__')), key=natural)


def read_data(data, path):
    """Build independent time or frequency signals from paired fields in one MAT."""
    signals = []
    for prefix in prefixes(data):
        axes = [suffix for suffix in ('t', 'f') if prefix+'_'+suffix in data]
        if len(axes) != 1:
            raise ValueError(f'{prefix}_u: expected exactly one corresponding {prefix}_t or {prefix}_f vector')
        suffix = axes[0]; domain = 'time' if suffix == 't' else 'frequency'
        key = prefix+'_'+suffix
        unit = text_value(data.get(prefix+'_unit', ''))
        axis_unit = text_value(data.get(key+'_unit', ''))
        axis = vector(data[key], key, real=True)*axis_scale(axis_unit, domain)
        if domain == 'frequency' and np.any(axis < 0): raise ValueError(f'{key}: frequencies must be nonnegative')
        name = text_value(data.get(prefix+'_name', prefix))
        signals.append(Signal(name or prefix, axis, vector(data[prefix+'_u'], prefix+'_u'), unit, domain=domain))
    return Recording(signals, str(path), timestamp(data))
