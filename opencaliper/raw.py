"""LTspice transient RAW writer."""
from pathlib import Path
import numpy as np


def variable(channel):
    """Map a voltage/current channel to a RAW trace name and variable type."""
    unit = channel.unit.upper()
    if unit in ('V', 'VOLT', 'VOLTS'):
        return f'V(Channel_{channel.number})', 'voltage'
    if unit in ('A', 'AMP', 'AMPERE', 'AMPERES'):
        return f'I(Channel_{channel.number})', 'current'
    raise ValueError(f'Channel{channel.number}: Einheit {channel.unit!r} ist weder Volt noch Ampere.')


def write_raw(meas, output, overwrite=False, double_precision=True, chunk_size=262144, start_at_zero=True):
    """Write an interleaved transient RAW file with a UTF-16LE header.
    
    @param meas Measurement of finite voltage/current samples on a shared uniform axis.
    @param output Destination path.
    @param overwrite Whether an existing output may be replaced.
    @param double_precision Use float64 amplitudes; otherwise use float32.
    @param chunk_size Number of records to write per temporary block.
    @param start_at_zero Start output at zero; otherwise use meas.xoffset.
    @return Destination Path.
    @exception ValueError Unsupported units, nonfinite/unequal samples or negative time origin.
    @exception FileExistsError Existing destination with overwrite disabled.
    
    Time values always use float64. The original origin is recorded in the title;
    this writer does not quantize amplitudes into waveform integer codes."""
    output = Path(output)
    n = len(meas.channels[0].samples)
    time_offset = 0.0 if start_at_zero else meas.xoffset
    if time_offset < 0:
        raise ValueError('Negative RAW-Zeiten sind LTspice-Kompressionsmarker; START_AT_ZERO=True setzen.')
    definitions = [variable(c) for c in meas.channels]
    for channel in meas.channels:
        if len(channel.samples) != n or not np.isfinite(channel.samples).all():
            raise ValueError('RAW erfordert gleich lange Kanäle mit endlichen Werten; NaN/Inf gefunden.')
        if not double_precision and np.max(np.abs(channel.samples)) > np.finfo(np.float32).max:
            raise ValueError('Signal überschreitet float32; DOUBLE_PRECISION=True setzen.')
    fields = [('time', '<f8')] + [(f'ch{i}', '<f8' if double_precision else '<f4')
                               for i in range(len(meas.channels))]
    dtype = np.dtype(fields)
    lines = [f'Title: * Imported oscilloscope measurement (source t0={meas.xoffset:.17g} s)',
             f'Date: {meas.timestamp:%Y-%m-%d %H:%M:%S}',
             'Plotname: Transient Analysis',
             'Flags: real forward' + (' double' if double_precision else ''),
             f'No. Variables: {len(meas.channels)+1}', f'No. Points: {n}',
             'Offset: 0', 'Command: LTspice RAW export via OpenCaliper', 'Variables:', '\t0\ttime\ttime']
    lines += [f'\t{i}\t{name}\t{unit}' for i, (name, unit) in enumerate(definitions, 1)]
    content = ('\n'.join(lines) + '\nBinary:\n').encode('utf-16-le')
    with output.open('wb' if overwrite else 'xb') as f:
        f.write(content)
        for start in range(0, n, chunk_size):
            stop = min(start + chunk_size, n)
            block = np.empty(stop - start, dtype=dtype)
            block['time'] = time_offset + np.arange(start, stop, dtype=np.float64) * meas.xinc
            for i, channel in enumerate(meas.channels):
                block[f'ch{i}'] = channel.samples[start:stop]
            block.tofile(f)
    return output

