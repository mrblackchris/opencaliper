"""LTspice transient and AC RAW, including stepped recordings.

Time axes become seconds; frequency axes become Hz. Complex AC voltage/current
samples remain complex in the Recording. They are not inferred S-parameters.
"""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording



def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    from spicelib import RawRead
    raw = RawRead(str(path), traces_to_read='*')
    if len(raw.get_plot_names()) != 1:
        raise ValueError('RAW import supports one plot per file; export each simulation plot separately')
    names = raw.get_trace_names()
    if not names or names[0].lower() not in ('time', 'frequency'):
        raise ValueError('RAW import requires a time or frequency axis; DC/operating-point sweeps are not supported')
    domain = 'time' if names[0].lower() == 'time' else 'frequency'
    signals = []
    steps = list(raw.get_steps())
    for step in steps:
        axis = np.asarray(raw.get_axis(step))
        # AC RAW stores frequency in a complex slot with a zero imaginary part.
        # Validate it before extracting real Hz; never silently discard an axis.
        if np.iscomplexobj(axis):
            if np.any(axis.imag != 0): raise ValueError('RAW horizontal axis must be real')
            axis = axis.real
        if domain == 'frequency' and np.any(axis < 0):
            raise ValueError('RAW frequencies must be nonnegative')
        for name in names[1:]:
            trace = raw.get_trace(name)
            signals.append(Signal(name + (f' / step {step}' if len(steps)>1 else ''),
                                  axis, trace.get_wave(step),
                                  {'voltage':'V','current':'A'}.get(trace.whattype, trace.whattype),
                                  domain=domain))
    if not signals: raise ValueError('RAW file contains no signal traces')
    return Recording(signals, str(path))
