"""Keysight AG binary normal/average time waveforms."""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording
import struct


def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    signals = []
    with path.open('rb') as f:
        header = f.read(12)
        if len(header) != 12 or header[:2] != b'AG':
            raise ValueError('Expected Keysight AG binary waveform file')
        _, _, size, count = struct.unpack('<2s2sII', header)
        if size != path.stat().st_size:
            raise ValueError('Truncated Keysight file or invalid file size')
        for index in range(count):
            start = f.tell()
            h = f.read(140)
            if len(h) != 140:
                raise ValueError('Truncated waveform header')
            length, kind, buffers, points = struct.unpack_from('<4I', h)
            if length < 140 or kind not in (1, 3):
                raise ValueError('Only normal/average Keysight waveforms are supported')
            dx, origin = struct.unpack_from('<dd', h, 32)
            xu, yu = struct.unpack_from('<II', h, 48)
            if xu != 2 or dx <= 0:
                raise ValueError('Expected a time waveform with positive sample interval')
            name = h[112:128].split(b'\0')[0].decode('ascii', errors='replace').strip() or f'Channel{index+1}'
            f.seek(start + length)
            for j in range(buffers):
                pos = f.tell()
                bh = f.read(12)
                if len(bh) != 12:
                    raise ValueError('Truncated waveform data header')
                hl, bt, width, size = struct.unpack('<IHHI', bh)
                if hl < 12 or bt not in (1, 2, 3) or width != 4 or size != points*4:
                    raise ValueError('Unsupported Keysight buffer type or length')
                f.seek(pos + hl)
                payload = f.read(size)
                if len(payload) != size:
                    raise ValueError('Truncated waveform samples')
                y = np.frombuffer(payload, '<f4').copy()
                signals.append(Signal(name + (f' / buffer {j+1}' if buffers > 1 else ''),
                                      origin + np.arange(points)*dx, y, {1:'V',4:'A'}.get(yu,'')))
    return Recording(signals, str(path))
