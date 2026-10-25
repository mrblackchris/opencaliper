"""Acquisition MAT reader and waveform export helpers."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import struct
import warnings

import numpy as np
from scipy.io import loadmat


@dataclass
class Channel:
    """Decoded acquisition channel: number, unit, samples, resolution and offset."""
    number: int
    unit: str
    samples: np.ndarray
    resolution: float
    offset: float


@dataclass
class Measurement:
    """Channels on a shared uniform axis with xinc, physical xoffset and timestamp."""
    channels: list
    xinc: float
    xoffset: float
    timestamp: datetime


def scalar(value, name):
    """Extract a finite numeric scalar, rejecting nonscalar or nonfinite metadata."""
    a = np.asarray(value)
    if a.size != 1:
        raise ValueError(f'{name}: einzelner Wert erwartet, erhalten: {a.shape}')
    result = float(a.item())
    if not np.isfinite(result):
        raise ValueError(f'{name}: muss endlich sein')
    return result


def text_value(value):
    """Normalize a MATLAB text array or scalar wrapper to stripped Python text."""
    a = np.asarray(value)
    if a.dtype.kind in 'US':
        return ''.join(str(x.decode() if isinstance(x, bytes) else x) for x in a.flat).strip().strip('"')
    if a.dtype.kind == 'O' and a.size == 1:
        return text_value(a.item())
    if a.size == 1:
        return str(a.item()).strip().strip('"')
    raise ValueError('Kein MATLAB-Textwert')


def load_mat(path):
    """Read classic or HDF5 MATLAB storage without interpreting channel fields.
    
    @param path pathlib.Path of the input MAT file.
    @return Dictionary of stored variables.
    
    The file signature selects scipy.io.loadmat or hdf5storage.loadmat."""
    with path.open('rb') as f:
        signature = f.read(520)
    if signature.startswith(b'\x89HDF') or signature[512:520] == b'\x89HDF\r\n\x1a\n':
        try:
            import hdf5storage
        except ImportError as exc:
            raise ImportError('Für diese MAT-Datei: python -m pip install hdf5storage') from exc
        return hdf5storage.loadmat(str(path), appendmat=False)
    return loadmat(str(path), squeeze_me=False, chars_as_strings=True)


def timestamp(vd):
    """Read optional MAT acquisition metadata; use the epoch if unrecognized.

    ISO recording_timestamp takes precedence over recognized date/time pairs.
    Missing, malformed or ambiguous metadata never blocks waveform loading and
    emits no warning. The default means unknown, not a measured acquisition date.
    """
    fallback = datetime(1970, 1, 1)
    if 'recording_timestamp' in vd:
        try:
            value = text_value(vd['recording_timestamp'])
            return datetime.fromisoformat(value[:-1]+'+00:00' if value.endswith('Z') else value)
        except (ValueError, TypeError, OverflowError, UnicodeError):
            pass
    if 'date' not in vd or 'time' not in vd:
        return fallback
    try:
        date = text_value(vd['date'])
        time = text_value(vd['time'])
    except (ValueError, TypeError, OverflowError, UnicodeError):
        return fallback
    dates = set()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%d%b%Y'):
        try:
            dates.add(datetime.strptime(date.upper(), fmt).date())
        except ValueError:
            pass
    if date.isdigit() and 6 <= len(date) <= 8:
        for cut in (5, 6):
            month, day = date[4:cut], date[cut:]
            if len(month) in (1, 2) and len(day) in (1, 2):
                try:
                    dates.add(datetime(int(date[:4]), int(month), int(day)).date())
                except ValueError:
                    pass
    times = set()
    if ':' in time:
        for fmt in ('%H:%M:%S.%f', '%H:%M:%S'):
            try:
                times.add(datetime.strptime(time, fmt).time())
            except ValueError:
                pass
    elif time.isdigit():
        for i in (1, 2):
            for j in (1, 2):
                if len(time) - i - j not in (1, 2):
                    continue
                try:
                    times.add(datetime(1970, 1, 1, int(time[:i]), int(time[i:i+j]), int(time[i+j:])).time())
                except ValueError:
                    pass
    if len(dates) != 1 or len(times) != 1:
        return fallback
    return datetime.combine(dates.pop(), times.pop())


def quantize(values):
    """Quantize physical values into signed IS2 samples.
    
    @param values Numeric amplitude array.
    @return Tuple of int16 samples, physical resolution and offset.
    
    Code -32768 denotes invalid data. Finite values use the remaining range;
    reconstruction error is at most half a resolution step apart from rounding."""
    finite = np.isfinite(values)
    if not finite.all():
        warnings.warn(f'{np.count_nonzero(~finite)} NaN/Inf-Werte als IllegalData (-32768) gespeichert.')
    raw = np.full(values.shape, -32768, dtype='<i2')
    if not finite.any():
        return raw, 1.0, 0.0
    low, high = float(values[finite].min()), float(values[finite].max())
    offset = low / 2 + high / 2
    resolution = high / 65534 - low / 65534 if high != low else 1.0
    if resolution <= 0 or not np.isfinite(resolution):
        raise ValueError('Signalbereich ist für IS2-Skalierung zu klein/groß.')
    with np.errstate(over='raise', invalid='raise'):
        scaled = np.rint((values[finite] - offset) / resolution)
    raw[finite] = np.clip(scaled, -32767, 32767).astype('<i2')
    return raw, resolution, offset


def read_measurement(filename, data_mode='auto', date_override=None, time_override=None, *, quantize_output=True):
    """Decode the ChannelN_t1 acquisition convention.
    
    @param filename MAT path; a missing .mat suffix is appended.
    @param data_mode auto, physical or raw; auto interprets integer arrays as ADC codes.
    @param date_override Optional unambiguous replacement acquisition date.
    @param time_override Optional replacement acquisition time.
    @param quantize_output If True, prepare IS2 output; if False, retain physical values.
    @return Tuple of resolved input Path and Measurement.
    @exception ValueError Invalid sampling timing, channel shape, ADC type or units. Optional acquisition date/time metadata never blocks loading.
    
    Float samples are already physical. Raw uint8/uint16 samples use midscale,
    yinc and offset. The time origin is xorg minus xref times xinc. Importers should
    use quantize_output=False to avoid unnecessary waveform quantization."""
    path = Path(filename).expanduser()
    if path.suffix.lower() != '.mat':
        path = Path(str(path) + '.mat')
    vd = load_mat(path)
    if data_mode not in ('auto', 'physical', 'raw'):
        raise ValueError('DATA_MODE muss auto, physical oder raw sein.')
    if date_override is not None:
        vd['date'] = date_override
    if time_override is not None:
        vd['time'] = time_override
    xinc = scalar(vd['xinc'], 'xinc')
    if xinc <= 0:
        raise ValueError('xinc muss positiv sein.')
    xoffset = scalar(vd.get('xorg', 0), 'xorg') - scalar(vd.get('xref', 0), 'xref') * xinc
    points = scalar(vd['points'], 'points')
    if points < 1 or not points.is_integer():
        raise ValueError('points muss eine positive Ganzzahl sein.')
    numbers = sorted(int(m.group(1)) for key in vd if (m := re.fullmatch(r'Channel(\d+)_t1', key)))
    if not numbers:
        raise ValueError('Keine ChannelN_t1-Signale in MAT-Datei gefunden.')
    channels = []
    for number in numbers:
        prefix = f'Channel{number}'
        original = np.asarray(vd[prefix + '_t1'])
        if original.dtype.kind not in 'fiu' or sum(s > 1 for s in original.shape) > 1:
            raise ValueError(f'{prefix}: reeller Signalvektor erwartet.')
        if original.size != int(points):
            raise ValueError(f'{prefix}: {original.size} Samples, points={int(points)}.')
        values = original.astype(np.float64).ravel()
        raw = data_mode == 'raw' or (data_mode == 'auto' and original.dtype.kind in 'iu')
        if raw:
            if original.dtype.kind != 'u' or original.dtype.itemsize not in (1, 2):
                raise ValueError(f'{prefix}: Rohdaten müssen uint8 oder uint16 sein; DATA_MODE prüfen.')
            yinc = scalar(vd[prefix + '_yinc'], prefix + '_yinc')
            if yinc <= 0:
                raise ValueError(f'{prefix}: yinc muss positiv sein.')
            offset = scalar(vd[prefix + '_offset'], prefix + '_offset')
            values = (values - 2 ** (original.dtype.itemsize * 8 - 1)) * yinc + offset
        unit = text_value(vd.get(prefix + '_unit', '?'))
        if not unit or any(c.isspace() for c in unit) or not unit.isascii():
            raise ValueError(f'{prefix}: Einheit muss ein einzelnes ASCII-Token sein: {unit!r}')
        if quantize_output:
            samples, resolution, offset = quantize(values)
        else:
            samples, resolution, offset = values, 1.0, 0.0
        channels.append(Channel(number, unit, samples, resolution, offset))
    return path, Measurement(channels, xinc, xoffset, timestamp(vd))


def header(meas, endian='Ltl', data_format='Block', data_offset=0, model='OpenCaliper'):
    """Build the ASCII waveform metadata header for uniformly sampled channels."""
    channels = meas.channels
    n = len(channels)
    lines = ['//YOKOGAWA ASCII FILE FORMAT', '', '$PublicInfo']

    def row(key, values):
        if not isinstance(values, (list, tuple)):
            values = [values]
        lines.append(f'{key:<20}' + ' '.join(str(v) for v in values))

    for key, value in [('FormatVersion', '1.02'), ('Model', model), ('Endian', endian),
                       ('DataFormat', data_format), ('GroupNumber', 1),
                       ('TraceTotalNumber', n), ('DataOffset', data_offset)]:
        row(key, value)
    lines.extend(['', '$Group1'])
    row('TraceNumber', n)
    row('BlockNumber', 1)
    row('TraceName', [f'Channel_{c.number}' for c in channels])
    row('BlockSize', [len(c.samples) for c in channels])
    row('VResolution', [format(c.resolution, '.17g') for c in channels])
    row('VOffset', [format(c.offset, '.17g') for c in channels])
    row('VDataType', ['IS2'] * n)
    row('VUnit', [c.unit for c in channels])
    for key, value in [('VPlusOverData', '?'), ('VMinusOverData', '?'),
                       ('VIllegalData', -32768), ('VMaxData', 32767), ('VMinData', -32767),
                       ('HResolution', format(meas.xinc, '.17g')),
                       ('HOffset', format(meas.xoffset, '.17g')), ('HUnit', 's'),
                       ('Date', meas.timestamp.strftime('%Y/%m/%d')),
                       ('Time', meas.timestamp.strftime('%H:%M:%S.%f'))]:
        row(key, [value] * n)
    return '\n'.join(lines) + '\n'


def write_wvf(meas, output, overwrite=False):
    """Write waveform data and its companion HDR file.
    
    @param meas Measurement containing prepared IS2 channel samples.
    @param output Destination WVF path.
    @param overwrite Whether existing output files may be replaced.
    @return Tuple of WVF and HDR paths."""
    output = Path(output)
    hdr = output.with_suffix('.hdr')
    content = header(meas).encode('ascii')
    if not overwrite and (output.exists() or hdr.exists()):
        raise FileExistsError(f'{output} oder {hdr} existiert bereits (OVERWRITE=False).')
    with output.open('wb' if overwrite else 'xb') as f:
        for channel in meas.channels:
            channel.samples.astype('<i2', copy=False).tofile(f)
    with hdr.open('wb' if overwrite else 'xb') as f:
        f.write(content)
    return output, hdr


def write_wdf(meas, output, overwrite=False):
    """Write the internal WDF converter output; not exposed by core export or the GUI."""
    output = Path(output)
    # Die 64-Byte-Struktur und Versionsbytes stammen aus der Referenzdatei.
    common = bytearray(64)
    common[:8] = b'%WDF' + struct.pack('>I', 64)
    common[8:12] = b'\x01\0\0\0'
    producer = b'OpenCaliper'
    common[32:32+len(producer)] = producer
    data_offset = len(common) + 12 + 8
    count = sum(c.samples.nbytes for c in meas.channels)
    if count > 0xffffffff:
        raise ValueError('WDF >4 GiB benötigt Mehrdatei-Aufteilung; hier nicht unterstützt.')
    info = header(meas, 'Big', 'Trace', data_offset).replace('FormatVersion       1.02', 'FormatVersion       1.01')
    info += '\n$PrivateInfo\nDisplayPointNo.     0\nStartOffset1        ' + ' '.join(['0'] * len(meas.channels)) + '\nDataEnd\n'
    with output.open('wb' if overwrite else 'xb') as f:
        f.write(common)
        f.write(b'DrAW' + struct.pack('>Q', count + 8))
        f.write(struct.pack('>II', count, 0xffffffff))
        for channel in meas.channels:
            channel.samples.astype('>i2').tofile(f)
        f.write(b'\xff' * 4)
        content = info.encode('ascii')
        f.write(b'XHDR' + struct.pack('>Q', len(content)) + content + b'\xff' * 4)
        f.write(b'FeND' + struct.pack('>Q', 0) + b'\xff' * 4)
    return output


def convert(filename, kind, *, data_mode='auto', date_override=None, time_override=None, overwrite=False):
    """Legacy helper for direct acquisition MAT conversion to a waveform writer."""
    path, meas = read_measurement(filename, data_mode, date_override, time_override)
    output = path.with_suffix('.' + kind)
    result = write_wvf(meas, output, overwrite) if kind == 'wvf' else write_wdf(meas, output, overwrite)
    print(f'{path.name}: {len(meas.channels)} Kanäle, {len(meas.channels[0].samples)} Samples/Kanal → {result}')
    if kind == 'wdf':
        print('Minimal-WDF geschrieben. Kompatibilität mit Yokogawa-Software noch nicht bestätigt.')
    return result
