"""MDF/MF4 numeric scalar channels, including labelled states."""
from pathlib import Path
from ..core import Signal, Recording



def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    from asammdf import MDF
    with MDF(path) as m:
        signals = []
        for group_index, group in enumerate(m.groups):
            for channel_index, channel in enumerate(group.channels):
                if channel_index == m.masters_db.get(group_index):
                    continue
                # Retain numeric enum/state channels instead of converting
                # their samples to labels, which the viewer cannot plot.
                # Other conversions (for example gain/offset) still apply.
                s = m.get(group=group_index, index=channel_index, raw=True)
                s = s.physical(ignore_value2text_conversions=True)
                if s.samples.dtype.kind in 'biufc' and s.samples.ndim == 1 and len(s.samples):
                    signals.append(Signal(s.name, s.timestamps, s.samples, s.unit))
        if not signals:
            raise ValueError('MDF contains no supported nonempty numeric scalar channels; '
                             'text, array and structured/bus channels cannot be plotted')
        return Recording(signals, str(path), m.start_time)
