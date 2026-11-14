"""Pre-parse MAT layouts, preserving acquisition, receiver and native formats."""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording
import re


def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    from ..acquisition import load_mat, read_measurement, text_value, timestamp
    from .matpreparse import detect_layouts
    data = load_mat(path)
    layouts = detect_layouts(data)
    signals = []
    keys = sorted((key for key in data if re.fullmatch(r'signal_\d+_values', key)),
                  key=lambda key: int(key.split('_')[1]))
    for key in keys:
        if key.startswith('signal_') and key.endswith('_values'):
            prefix = key[:-6]
            missing = [prefix+field for field in ('name', 'time', 'unit') if prefix+field not in data]
            if missing: raise ValueError('Incomplete OpenCaliper MAT channel; missing '+', '.join(missing))
            signals.append(Signal(text_value(data[prefix+'name']), data[prefix+'time'],
                                  data[key], text_value(data[prefix+'unit']),
                                  domain=text_value(data[prefix+'domain']) if prefix+'domain' in data else 'time',
                                  reference_impedance=float(np.asarray(data[prefix+'reference_impedance']).item())
                                  if prefix+'reference_impedance' in data else None))
    if 'paired' in layouts:
        from .pairedconvert import read_data
        signals.extend(read_data(data, path).signals)
    if 'receiver' in layouts:
        from .esrpconvert import read_data
        signals.extend(read_data(data, path).signals)
    if 'acquisition' in layouts:
        _, m = read_measurement(path, quantize_output=False)
        signals.extend(Signal(f'Channel{c.number}', m.xoffset + np.arange(len(c.samples))*m.xinc,
                              c.samples, c.unit) for c in m.channels)
    if not signals:
        raise ValueError('Unsupported MAT layout: expected PREFIX_u with PREFIX_t/PREFIX_f, ChannelN_t1 with points/xinc, ESRP freq + avg/peak/qpk (or pk), or OpenCaliper MAT')
    return Recording(signals, str(path), timestamp(data))
