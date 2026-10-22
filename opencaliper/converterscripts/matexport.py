"""Native OpenCaliper MAT: independent time axes, names, units and timestamp."""
from pathlib import Path
from scipy.io import savemat


def write(recording, path, overwrite=False):
    """Write a Recording; the dispatcher validates overwrite and nonempty input."""
    path = Path(path)
    data = {'recording_timestamp': recording.timestamp.isoformat()}
    for i, s in enumerate(recording.signals):
        p = f'signal_{i}_'
        data.update({p+'name': s.name, p+'unit': s.unit, p+'time': s.time, p+'values': s.values, p+'domain': s.domain})
    with path.open('wb' if overwrite else 'xb') as f:
        savemat(f, data, do_compression=True)
