"""Yokogawa single-block IS2 waveforms with companion HDR."""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording
import shlex


def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    hdrpath = path.with_suffix('.hdr')
    if not hdrpath.exists():
        hdrpath = path.with_suffix('.HDR')
    sections, current = [], {}
    for line in hdrpath.read_text().splitlines():
        if line.startswith('$Group'):
            current = {}; sections.append(current)
        elif line.strip() and not line.startswith(('//', '$')):
            parts = shlex.split(line)
            current[parts[0]] = parts[1:]
    # Public metadata is read separately to avoid group keys overwriting each other.
    public = {}
    for line in hdrpath.read_text().split('$Group')[0].splitlines():
        parts = line.split()
        if parts and not parts[0].startswith(('/', '$')):
            public[parts[0]] = parts[1:]
    if public.get('DataFormat') != ['Block']:
        raise ValueError('Only Yokogawa Block format is supported')
    endian = '>' if public.get('Endian') == ['Big'] else '<'
    signals = []
    with path.open('rb') as f:
        f.seek(int(public.get('DataOffset', ['0'])[0]))
        for group in sections:
            if int(group.get('BlockNumber', ['1'])[0]) != 1:
                raise ValueError('Multi-block WVF is not supported yet')
            for i in range(int(group['TraceNumber'][0])):
                def value(key, default=None):
                    v = group.get(key, [default]); return v[i] if len(v)>1 else v[0]
                if value('VDataType') != 'IS2':
                    raise ValueError('Only Yokogawa IS2 samples are supported')
                n = int(value('BlockSize'))
                raw = np.fromfile(f, endian+'i2', count=n)
                if len(raw) != n:
                    raise ValueError('Truncated WVF data')
                y = raw.astype(float)*float(value('VResolution')) + float(value('VOffset'))
                y[raw == -32768] = np.nan
                signals.append(Signal(value('TraceName'), float(value('HOffset')) + np.arange(n)*float(value('HResolution')), y, value('VUnit', '')))
    return Recording(signals, str(path))
