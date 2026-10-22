"""Acquisition MAT and native OpenCaliper interchange MAT."""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording
import re
from datetime import datetime


def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    from ..acquisition import load_mat, read_measurement, text_value
    data = load_mat(path)
    if 'freq' in data and any(key in data for key in ('avg', 'pk', 'qpk')):
        from .esrpconvert import read_data
        return read_data(data, path)
    if 'xinc' in data and 'points' in data:
        _, m = read_measurement(path, quantize_output=False)
        return Recording([Signal(f'Channel{c.number}', m.xoffset + np.arange(len(c.samples))*m.xinc,
                                 c.samples, c.unit) for c in m.channels], str(path), m.timestamp)
    signals = []
    keys = sorted((key for key in data if re.fullmatch(r'signal_\d+_values', key)),
                  key=lambda key: int(key.split('_')[1]))
    for key in keys:
        if key.startswith('signal_') and key.endswith('_values'):
            prefix = key[:-6]
            signals.append(Signal(text_value(data[prefix+'name']), data[prefix+'time'],
                                  data[key], text_value(data[prefix+'unit']),
                                  domain=text_value(data[prefix+'domain']) if prefix+'domain' in data else 'time'))
    if not signals:
        raise ValueError('Unsupported MAT layout: expected ChannelN_t1 acquisition data with points/xinc, ESRP freq + avg/pk/qpk, or OpenCaliper MAT')
    return Recording(signals, str(path), datetime.fromisoformat(text_value(data['recording_timestamp'])) if 'recording_timestamp' in data else datetime(1970, 1, 1))
