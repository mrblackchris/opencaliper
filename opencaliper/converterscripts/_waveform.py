"""Shared validation and conversion for uniform real waveform exports."""
import numpy as np


def measurement(recording, quantized=False):
    from ..acquisition import Channel, Measurement, quantize
    if any(s.domain != "time" for s in recording.signals):
        raise ValueError("Waveform export requires time-domain channels")
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
        samples, resolution, offset = quantize(s.values) if quantized else (s.values, 1, 0)
        channels.append(Channel(i, s.unit, samples, resolution, offset))
    m = Measurement(channels, dx, first.time[0], recording.timestamp)
    return m
