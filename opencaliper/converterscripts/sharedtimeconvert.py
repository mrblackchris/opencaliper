"""Explicit shared-axis MAT: t1 seconds, PREFIX_t1 amplitude vectors."""
import re
from ..core import Recording, Signal
from ..acquisition import text_value, timestamp
from .pairedconvert import vector, axis_scale


def channel_keys(data):
    """Find amplitude arrays without treating optional metadata as channels."""
    return sorted((key for key in data if re.fullmatch(r'.+_t1', key)),
                  key=lambda key: [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', key)])


def read_data(data, path):
    """Use the explicit common vector; do not infer timing from xinc or points."""
    axis = vector(data['t1'], 't1', real=True)*axis_scale(text_value(data.get('t1_unit', 's')), 'time')
    signals = []
    for key in channel_keys(data):
        prefix = key[:-3]
        if text_value(data.get(prefix+'_domain', 'time')) != 'time':
            raise ValueError(f'{key}: shared t1 data must be time-domain')
        signals.append(Signal(text_value(data.get(prefix+'_name', prefix)), axis,
                              vector(data[key], key), text_value(data.get(prefix+'_unit', ''))))
    return Recording(signals, str(path), timestamp(data))
