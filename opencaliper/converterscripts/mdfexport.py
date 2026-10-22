"""MDF 3.30 (.mdf) and MDF 4.10 (.mf4) export."""
from pathlib import Path
from datetime import timezone
import numpy as np
import tempfile
import shutil


def write(recording, path, overwrite=False):
    """Write a Recording; the dispatcher validates overwrite and nonempty input."""
    if any(s.domain != "time" for s in recording.signals):
        raise ValueError("MDF export requires time-domain channels")
    path = Path(path)
    ext = path.suffix.lower()
    from asammdf import MDF, Signal as MSignal
    with MDF(version='3.30' if ext == '.mdf' else '4.10') as m:
        m.start_time = recording.timestamp if recording.timestamp.tzinfo else recording.timestamp.replace(tzinfo=timezone.utc)
        for s in recording.signals:
            if np.iscomplexobj(s.values):
                raise ValueError('Complex signals cannot be exported to MDF')
            m.append([MSignal(s.values, s.time, name=s.name, unit=s.unit)])
        # asammdf normalizes suffixes and may choose another filename on a
        # collision. Stage its output so our exact path/overwrite contract holds.
        with tempfile.TemporaryDirectory(dir=path.resolve().parent) as folder:
            staged = Path(folder) / ('measurement' + ext)
            m.save(staged, overwrite=True)
            with staged.open('rb') as source, path.open('wb' if overwrite else 'xb') as output:
                shutil.copyfileobj(source, output)
