"""Analysis operates on source samples, never display decimation."""
import numpy as np


def statistics(signal, start=None, stop=None):
    """Calculate descriptive statistics from original interval samples.
    
    @param signal Signal to analyze; complex amplitudes are replaced by magnitudes.
    @param start Inclusive lower horizontal bound, or None.
    @param stop Inclusive upper horizontal bound, or None.
    @return Dictionary with count, minimum, maximum, peak_to_peak, mean, rms and std.
    @exception ValueError Selected interval contains no finite samples.
    
    Nonfinite amplitudes are ignored. Standard deviation uses ddof=0. No
    interpolated boundary samples or display-decimated data enter the result."""
    _, y = signal.region(start, stop)
    if np.iscomplexobj(y):
        y = np.abs(y)
    y = y[np.isfinite(y)]
    if not len(y):
        raise ValueError('No finite samples in selected interval')
    return dict(count=int(len(y)), minimum=float(y.min()), maximum=float(y.max()),
                peak_to_peak=float(np.ptp(y)), mean=float(y.mean()),
                rms=float(np.sqrt(np.mean(y*y))), std=float(y.std()))


def fft(signal, start=None, stop=None):
    """Calculate a Hann-windowed one-sided peak-amplitude spectrum.
    
    @param signal Source signal with timestamps in seconds and real amplitudes.
    @param start Inclusive source-time lower bound in seconds, or None.
    @param stop Inclusive source-time upper bound in seconds, or None.
    @return Tuple of frequency bins in Hz and amplitudes in the source unit.
    @exception ValueError Fewer than four samples, nonfinite/complex amplitudes,
            or nonpositive/nonuniform sample spacing.
    
    The mean is removed before windowing. Amplitudes are normalized by the window
    sum, with DC and Nyquist endpoint adjustments. This is not a power spectral
    density or dB result; there is no automatic resampling."""
    t, y = signal.region(start, stop)
    if len(t) < 4 or np.iscomplexobj(y) or not np.isfinite(y).all():
        raise ValueError('FFT needs at least four finite real samples')
    dt = np.diff(t)
    if dt[0] <= 0 or not np.allclose(dt, dt[0], rtol=1e-4, atol=abs(dt[0])*1e-8):
        raise ValueError('FFT needs uniform samples; resample explicitly first')
    window = np.hanning(len(y))
    amplitude = np.abs(np.fft.rfft((y-y.mean())*window))*2/window.sum()
    amplitude[0] /= 2
    if len(y) % 2 == 0:
        amplitude[-1] /= 2
    return np.fft.rfftfreq(len(y), dt[0]), amplitude


def cursor_values(signal, a, b):
    """Interpolate two amplitudes and calculate their differences.
    
    @param signal Real-valued signal; its axis may represent seconds or FFT Hz.
    @param a First horizontal coordinate in the signal axis unit.
    @param b Second horizontal coordinate in the signal axis unit.
    @return Dictionary with a, b, delta, dt and frequency. dt is b minus a;
            frequency is its reciprocal magnitude, or None for zero separation.
    @exception ValueError Signal amplitudes are complex.
    
    Out-of-range amplitudes are NaN. The frequency field has Hz meaning only when
    the input axis is seconds. FFT readouts use horizontal differences in Hz."""
    if np.iscomplexobj(signal.values):
        raise ValueError('Cursor values require a real signal')
    ya, yb = np.interp([a, b], signal.time, signal.values, left=np.nan, right=np.nan)
    dt = b-a
    return dict(a=float(ya), b=float(yb), delta=float(yb-ya), dt=dt,
                frequency=1/abs(dt) if dt else None)
