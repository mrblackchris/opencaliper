"""Detect a format, select its adapter and convert to/from OpenCaliper data.

Run: python -m opencaliper.converterscripts input.mf4 [output.mat]
Omitting output creates input.opencaliper.mat beside the input. See README.md
for the in-memory Recording/Signal contract and native MAT disk layout.
"""
from pathlib import Path
import importlib
import argparse
import sys

# Support running this dispatcher by file path as well as with python -m.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'opencaliper.converterscripts'

from .formats import FORMATS


def detect_format(filename, writing=False):
    """Select a registered reader/writer by suffix, independent of letter case."""
    extension = Path(filename).suffix.lower()
    format = FORMATS.get(extension)
    module = (format.writer if writing else format.reader) if format else None
    if module is None:
        direction = 'output' if writing else 'input'
        raise ValueError(f'Unsupported {direction} format: {extension}')
    return format


def load(filename):
    """Read an external file into the same Recording consumed by the GUI."""
    path = Path(filename)
    format = detect_format(path)
    adapter = importlib.import_module(f'.{format.reader}', __package__)
    from ..core import Recording
    recording = adapter.read(path)
    if not isinstance(recording, Recording):
        raise TypeError(f'{format.reader}.read() must return a Recording')
    return recording


def export(recording, filename, overwrite=False):
    """Write a Recording through the chosen exporter; preserve overwrite checks."""
    path = Path(filename)
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    if not recording.signals:
        raise ValueError('No signals to export')
    format = detect_format(path, writing=True)
    if path.suffix.lower() != ".mat" and any(s.domain != "time" for s in recording.signals):
        raise ValueError("Frequency-domain channels must be exported as OpenCaliper MAT")
    adapter = importlib.import_module(f'.{format.writer}', __package__)
    adapter.write(recording, path, overwrite=overwrite)
    return path


def convert_file(filename, output=None, overwrite=False):
    """Convert any supported input to native MAT by default, or another export."""
    source = Path(filename)
    destination = Path(output) if output is not None else source.with_suffix('.opencaliper.mat')
    detect_format(destination, writing=True)
    if source.resolve() == destination.resolve():
        raise ValueError('Input and output paths must differ')
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    return export(load(source), destination, overwrite=overwrite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Measurement file; format detected from its suffix')
    parser.add_argument('output', nargs='?', help='Default: input.opencaliper.mat')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(convert_file(args.input, args.output, args.overwrite))
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
