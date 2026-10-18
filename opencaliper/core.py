"""Format adapters sharing independent, physical channel time axes."""
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
import shlex
import struct
import re
import numpy as np
from scipy.io import savemat


@dataclass
class Signal:
    """One channel with a horizontal axis and numeric sample values.
    
    @param name Human-readable channel name.
    @param time Nonempty finite nondecreasing timestamps in seconds.
    @param values Matching numeric amplitudes; complex and nonfinite values are allowed.
    @param unit Physical amplitude unit, or an empty string if unspecified.
    
    Arrays are flattened during initialization. Individual operations impose
    additional constraints. FFT display signals reuse time for frequency in Hz.
    The dataclass is mutable; display code should treat source arrays as read-only."""
    name: str
    time: np.ndarray
    values: np.ndarray
    unit: str = ""

    def __post_init__(self):
        self.time = np.asarray(self.time, dtype=float).reshape(-1)
        self.values = np.asarray(self.values).reshape(-1)
        if len(self.time) != len(self.values) or not len(self.time):
            raise ValueError(f"{self.name}: empty or mismatched samples")
        if not np.isfinite(self.time).all() or np.any(np.diff(self.time) < 0):
            raise ValueError(f"{self.name}: time must be finite and nondecreasing")
        if self.values.dtype.kind not in 'biufc':
            raise ValueError(f"{self.name}: numeric samples required")

    def region(self, start=None, stop=None):
        """Select existing samples in an inclusive horizontal interval.
        
        @param start Lower bound, or None for the beginning.
        @param stop Upper bound, or None for the end.
        @return Tuple of sliced axis and value arrays, possibly empty.
        
        Two supplied bounds are sorted. Boundary samples are not interpolated."""
        a, b = sorted((start, stop)) if start is not None and stop is not None else (start, stop)
        left = np.searchsorted(self.time, a) if a is not None else 0
        right = np.searchsorted(self.time, b, side='right') if b is not None else len(self.time)
        return self.time[left:right], self.values[left:right]



@dataclass
class Recording:
    """Group channels and their acquisition metadata.
    
    @param signals List of Signal objects, possibly with independent time axes.
    @param source Source path or descriptive string; empty for constructed data.
    @param timestamp Acquisition datetime; defaults to the naive Unix epoch.
    
    This container does not itself validate the channel list."""
    signals: list[Signal]
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime(1970, 1, 1))


def load(filename):
    """Read a supported file into physical signals and explicit time axes.
    
    @param filename Input path; its suffix selects the reader.
    @return Recording containing decoded channels and available metadata.
    @exception ValueError Unsupported format, layout or invalid sample data.
    @exception OSError Input or required companion file cannot be read.
    
    Supported inputs are MAT, MDF/MF4, Keysight BIN, WVF with HDR, and transient RAW.
    Acquisition MAT scaling happens before constructing Signal objects. This
    function does not create GUI widgets or resample channels."""
    path = Path(filename)
    ext = path.suffix.lower()
    if ext == '.mat':
        from .acquisition import load_mat, read_measurement, text_value
        data = load_mat(path)
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
                                      data[key], text_value(data[prefix+'unit'])))
        if not signals:
            raise ValueError('Unsupported MAT layout: expected ChannelN_t1 acquisition data with points/xinc, or OpenCaliper MAT')
        return Recording(signals, str(path), datetime.fromisoformat(text_value(data['recording_timestamp'])) if 'recording_timestamp' in data else datetime(1970, 1, 1))
    if ext in ('.mf4', '.mdf'):
        from asammdf import MDF
        with MDF(path) as m:
            signals = []
            for group_index, group in enumerate(m.groups):
                for channel_index, channel in enumerate(group.channels):
                    if channel_index == m.masters_db.get(group_index):
                        continue
                    s = m.get(group=group_index, index=channel_index)
                    if s.samples.dtype.kind in 'biufc' and s.samples.ndim == 1 and len(s.samples):
                        signals.append(Signal(s.name, s.timestamps, s.samples, s.unit))
            return Recording(signals, str(path), m.start_time)
    if ext == '.raw':
        from spicelib import RawRead
        raw = RawRead(str(path), traces_to_read='*')
        if len(raw.get_plot_names()) != 1 or raw.get_trace_names()[0].lower() != 'time':
            raise ValueError('RAW import currently supports one time-domain plot per file')
        signals = []
        steps = list(raw.get_steps())
        for step in steps:
            axis = raw.get_axis(step)
            for name in raw.get_trace_names()[1:]:
                trace = raw.get_trace(name)
                signals.append(Signal(name + (f' / step {step}' if len(steps)>1 else ''),
                                      axis, trace.get_wave(step),
                                      {'voltage':'V','current':'A'}.get(trace.whattype, trace.whattype)))
        return Recording(signals, str(path))
    if ext == '.bin':
        return _keysight(path)
    if ext == '.wvf':
        return _wvf(path)
    raise ValueError(f'Unsupported input format: {ext}')


def _keysight(path):
    """Decode supported AG normal/average float32 time-domain buffers."""
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


def _wvf(path):
    """Read single-block IS2 waveform samples using the companion HDR metadata."""
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


def export(recording, filename, overwrite=False):
    """Write loaded source signals in the format selected by the output suffix.
    
    @param recording Recording to export; it must contain at least one signal.
    @param filename Destination path, including the requested format suffix.
    @param overwrite Whether an existing destination may be replaced.
    @return Destination pathlib.Path.
    @exception FileExistsError Destination exists and overwrite is False.
    @exception ValueError Unsupported output or incompatible signal data.
    
    MAT preserves independent axes. RAW/WVF require real signals on identical
    uniform axes. WVF quantizes amplitudes; RAW starts time at zero and retains
    the original origin in its header. Conversion can discard device metadata."""
    path = Path(filename)
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    if not recording.signals:
        raise ValueError('No signals to export')
    ext = path.suffix.lower()
    if ext == '.mat':
        data = {'recording_timestamp': recording.timestamp.isoformat()}
        for i, s in enumerate(recording.signals):
            p = f'signal_{i}_'
            data.update({p+'name': s.name, p+'unit': s.unit, p+'time': s.time, p+'values': s.values})
        with path.open('wb' if overwrite else 'xb') as f:
            savemat(f, data, do_compression=True)
    elif ext in ('.mdf', '.mf4'):
        from asammdf import MDF, Signal as MSignal
        with MDF(version='3.30' if ext == '.mdf' else '4.10') as m:
            m.start_time = recording.timestamp if recording.timestamp.tzinfo else recording.timestamp.replace(tzinfo=timezone.utc)
            for s in recording.signals:
                if np.iscomplexobj(s.values):
                    raise ValueError('Complex signals cannot be exported to MDF')
                m.append([MSignal(s.values, s.time, name=s.name, unit=s.unit)])
            m.save(path, overwrite=overwrite)
    elif ext in ('.raw', '.wvf'):
        from .acquisition import Channel, Measurement, quantize, write_wvf
        from .raw import write_raw
        first = recording.signals[0]
        if len(first.time) < 2:
            raise ValueError('Export needs at least two samples')
        dx = first.time[1]-first.time[0]
        if dx <= 0 or not np.allclose(np.diff(first.time), dx, rtol=1e-6, atol=abs(dx)*1e-8):
            raise ValueError('Export requires uniform time samples; resample explicitly first')
        channels = []
        for i, s in enumerate(recording.signals, 1):
            if np.iscomplexobj(s.values) or not np.array_equal(first.time, s.time):
                raise ValueError('Export requires real signals on identical time axes')
            samples, resolution, offset = quantize(s.values) if ext == '.wvf' else (s.values, 1, 0)
            channels.append(Channel(i, s.unit, samples, resolution, offset))
        m = Measurement(channels, dx, first.time[0], recording.timestamp)
        if ext == '.raw':
            write_raw(m, path, overwrite=overwrite)
        else:
            write_wvf(m, path, overwrite=overwrite)
    else:
        raise ValueError(f'Unsupported output format: {ext}')
    return path
