"""LTspice transient RAW, including stepped recordings."""
from pathlib import Path
from ..core import Signal, Recording



def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
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
