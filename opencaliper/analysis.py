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


def fft(signal, start=None, stop=None, *, resample=False, sample_rate=None):
    """Calculate a Hann-windowed one-sided peak-amplitude spectrum.
    
    @param signal Source signal with timestamps in seconds and real amplitudes.
    @param start Inclusive source-time lower bound in seconds, or None.
    @param stop Inclusive source-time upper bound in seconds, or None.
    @param resample Enable explicit linear interpolation to uniform time samples.
    @param sample_rate Positive finite interpolation rate in Hz; None uses median spacing.
    @return Tuple of frequency bins in Hz and amplitudes in the source unit.
    @exception ValueError Fewer than four samples, nonfinite/complex amplitudes,
            or nonpositive/nonuniform sample spacing.
    
    The mean is removed before windowing. Amplitudes are normalized by the window
    sum, with DC and Nyquist endpoint adjustments. This is not a power spectral
    density or dB result. With resample=True, linearly interpolate the selected
    samples to a uniform grid before FFT. sample_rate is Hz; None chooses the
    reciprocal median source interval. Source arrays are never modified.
    Interpolation does not provide anti-alias filtering or recover missing detail."""
    if signal.domain != "time":
        raise ValueError("This channel is already frequency-domain data; open it in a Spectrum tab")
    t, y = signal.region(start, stop)
    if len(t) < 4:
        scope = 'full recording' if start is None and stop is None else f'time interval [{start}, {stop}] s'
        raise ValueError(f'FFT needs at least four samples; {scope} contains {len(t)} '
                         f'of {len(signal.time)} source samples. Widen the interval or use the full recording.')
    if np.iscomplexobj(y):
        raise ValueError('FFT requires real amplitudes; this channel contains complex values')
    invalid = int(np.count_nonzero(~np.isfinite(y)))
    if invalid:
        raise ValueError(f'FFT interval contains {invalid} NaN/Inf samples out of {len(y)}. '
                         'Select a continuous interval of finite samples; invalid samples are not dropped or filled.')
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError('FFT needs strictly increasing timestamps; duplicate timestamps must be resolved first')
    if sample_rate is not None and not resample:
        raise ValueError('Enable resampling to specify an FFT sample rate')
    if resample:
        rate = float(sample_rate) if sample_rate is not None else 1/float(np.median(dt))
        if not np.isfinite(rate) or rate <= 0:
            raise ValueError('FFT resampling rate must be finite and positive (Hz)')
        points = (t[-1]-t[0])*rate
        if not np.isfinite(points) or points >= 10_000_000:
            raise ValueError('FFT resampling exceeds 10 million samples; lower the rate or shorten the interval')
        count = int(np.floor(points+1e-8))+1
        if count < 4:
            raise ValueError('FFT resampling grid has fewer than four samples; increase the rate or widen the interval')
        grid = np.arange(count)/rate
        y = np.interp(grid, t-t[0], y)
        spacing = 1/rate
    else:
        spacing = dt[0]
        if not np.allclose(dt, spacing, rtol=1e-4, atol=abs(spacing)*1e-8):
            raise ValueError('FFT needs uniform samples. Enable “Resample (linear)” in the FFT tab, '
                             'choose a sample rate (or Auto), then click Recalculate')
    window = np.hanning(len(y))
    amplitude = np.abs(np.fft.rfft((y-y.mean())*window))*2/window.sum()
    amplitude[0] /= 2
    if len(y) % 2 == 0:
        amplitude[-1] /= 2
    return np.fft.rfftfreq(len(y), spacing), amplitude


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
