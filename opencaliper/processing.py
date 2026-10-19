"""Signal processing on original samples, independent of the desktop interface."""
import ast
import operator
import numpy as np
from scipy import signal as dsp
from scipy.integrate import cumulative_trapezoid
from .core import Signal


def uniform(signal):
    t, y = signal.time, signal.values
    if len(t) < 4 or np.iscomplexobj(y) or not np.isfinite(y).all():
        raise ValueError('At least four finite real samples are required')
    dt = np.diff(t)
    if dt[0] <= 0 or not np.allclose(dt, dt[0], rtol=1e-4, atol=dt[0]*1e-8):
        raise ValueError('Uniform, strictly increasing samples are required')
    return 1 / dt[0]


def expression(text, signals, name='Math', unit=''):
    """Evaluate arithmetic and approved unary functions; never execute Python code.

    Channels must share the exact time axis. Units are supplied by the user.
    """
    tree = ast.parse(text, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError('Expression is too long')
    used = [signals[n.id] for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in signals]
    if not used:
        raise ValueError('Expression must reference a channel')
    t = used[0].time
    if any(not np.array_equal(t, s.time) for s in used):
        raise ValueError('Channels must have identical time axes; align/resample first')
    binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
              ast.Div: operator.truediv}
    functions = {'abs': np.abs, 'sqrt': np.sqrt, 'sin': np.sin, 'cos': np.cos,
                 'differentiate': lambda y: np.gradient(y, t),
                 'integrate': lambda y: cumulative_trapezoid(y, t, initial=0)}
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Name) and node.id in signals: return signals[node.id].values
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            return binary[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and len(node.args) == 1 and not node.keywords:
            if node.func.id in ('differentiate', 'integrate') and np.any(np.diff(t) <= 0):
                raise ValueError('Calculus requires strictly increasing timestamps')
            return functions[node.func.id](visit(node.args[0]))
        raise ValueError('Use channels, numbers, + - * / and abs/sqrt/sin/cos/differentiate/integrate only')
    with np.errstate(all='raise'):
        y = np.broadcast_to(visit(tree), t.shape).copy()
    return Signal(name, t, y, unit)


def filtered(source, kind, frequency, order=4, quality=30):
    fs = uniform(source)
    if not 0 < frequency < fs/2:
        raise ValueError(f'Frequency must be between 0 and Nyquist ({fs/2:g} Hz)')
    if kind == 'notch':
        b, a = dsp.iirnotch(frequency, quality, fs)
        y = dsp.filtfilt(b, a, source.values)
    elif kind in ('lowpass', 'highpass'):
        sos = dsp.butter(order, frequency, btype=kind, fs=fs, output='sos')
        y = dsp.sosfiltfilt(sos, source.values)
    else: raise ValueError('Unknown filter type')
    return Signal(f'{source.name} {kind} {frequency:g} Hz', source.time, y, source.unit)


def aligned(source, reference):
    """Shift source timestamps to maximize demeaned cross-correlation on overlap."""
    fs = uniform(source)
    if not np.isclose(fs, uniform(reference), rtol=1e-4):
        raise ValueError('Cross-correlation requires matching sample rates')
    lo, hi = max(source.time[0], reference.time[0]), min(source.time[-1], reference.time[-1])
    t = reference.time[(reference.time >= lo) & (reference.time <= hi)]
    if len(t) < 4: raise ValueError('At least four overlapping samples are required')
    a = np.interp(t, reference.time, reference.values)
    b = np.interp(t, source.time, source.values)
    a, b = a-a.mean(), b-b.mean()
    if not np.any(a) or not np.any(b): raise ValueError('Cannot align a constant signal')
    corr = dsp.correlate(a, b, method='fft')
    lag = dsp.correlation_lags(len(a), len(b))[np.argmax(corr)]
    shift = float(lag/fs)
    return Signal(f'{source.name} aligned ({shift:+g} s)', source.time+shift, source.values, source.unit)


def events(source, kind, threshold, distance=1):
    """Return event timestamps for rising/falling crossings, peaks, pulses or outliers."""
    y, t = source.values, source.time
    if np.iscomplexobj(y) or not np.isfinite(y).all(): raise ValueError('Finite real samples required')
    if kind in ('rising', 'falling', 'pulses'):
        up = (y[:-1] < threshold) & (y[1:] >= threshold)
        down = (y[:-1] > threshold) & (y[1:] <= threshold)
        indices = np.flatnonzero(up if kind == 'rising' else down if kind == 'falling' else up | down)
        return t[indices]+(threshold-y[indices])/(y[indices+1]-y[indices])*(t[indices+1]-t[indices])
    if kind == 'peaks': return t[dsp.find_peaks(y, height=threshold, distance=distance)[0]]
    if kind == 'outliers':
        if threshold <= 0: raise ValueError('Outlier standard-deviation threshold must be positive')
        return t[np.abs(y-y.mean()) > threshold*y.std()]
    raise ValueError('Unknown event type')


def spectrogram(source, segment=256, overlap=0.5):
    fs = uniform(source)
    if segment < 4 or segment > len(source.time) or not 0 <= overlap < 1:
        raise ValueError('Segment must fit the recording; overlap must be in [0, 1)')
    f, t, power = dsp.spectrogram(source.values, fs, window='hann', nperseg=segment,
                                 noverlap=int(segment*overlap), scaling='density')
    return t+source.time[0], f, 10*np.log10(np.maximum(power, np.finfo(float).tiny))
