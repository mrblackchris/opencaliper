"""Command line entry points; GUI dependencies are loaded only for gui."""
import argparse
import json
import sys
from .core import load
from .analysis import statistics, fft


def main(argv=None):
    """Dispatch GUI, info, convert, stats and FFT commands.
    
    @param argv Argument list without program name, or None to read sys.argv.
    @return Exit status: zero on success, one for a handled runtime failure.
    
    Argparse handles invalid command syntax. GUI dependencies are imported only
    for the gui command. FFT CSV output refuses an existing file."""
    p = argparse.ArgumentParser(prog='opencaliper')
    sub = p.add_subparsers(dest='command', required=True)
    gui = sub.add_parser('gui'); gui.add_argument('files', nargs='*')
    info = sub.add_parser('info'); info.add_argument('input')
    convert = sub.add_parser('convert'); convert.add_argument('input'); convert.add_argument('output')
    convert.add_argument('--overwrite', action='store_true')
    for name in ('stats', 'fft'):
        a = sub.add_parser(name); a.add_argument('input'); a.add_argument('--signal', type=int, default=0)
        a.add_argument('--start', type=float); a.add_argument('--stop', type=float)
        if name == 'fft':
            a.add_argument('output', help='CSV output (frequency_Hz, amplitude)')
            a.add_argument('--resample', action='store_true', help='Linearly interpolate to uniform time samples')
            a.add_argument('--sample-rate', type=float, help='Resampling rate in Hz; default: reciprocal median interval')
    args = p.parse_args(argv)
    try:
        if args.command == 'gui':
            from .gui import run
            return run(args.files)
        if args.command == 'convert':
            from .converterscripts.convert import convert_file
            print(convert_file(args.input, args.output, args.overwrite))
            return 0
        r = load(args.input)
        if args.command == 'info':
            print(json.dumps([dict(index=i, name=s.name, unit=s.unit, domain=s.domain,
                                   axis_unit="s" if s.domain == "time" else "Hz", samples=len(s.time),
                                   start=float(s.time[0]), stop=float(s.time[-1])) for i,s in enumerate(r.signals)], indent=2))
        else:
            if not 0 <= args.signal < len(r.signals):
                raise ValueError('Signal index out of range; use info to list signals')
            s = r.signals[args.signal]
            if args.command == 'stats':
                print(json.dumps(statistics(s, args.start, args.stop), indent=2))
            else:
                import numpy as np
                f, a = fft(s, args.start, args.stop, resample=args.resample, sample_rate=args.sample_rate)
                with open(args.output, 'x') as output:
                    np.savetxt(output, np.column_stack((f,a)), delimiter=',', header='frequency_Hz,amplitude', comments='')
        return 0
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


def mat2raw():
    """Console shortcut that parses MAT/RAW paths and delegates to the convert command."""
    p = argparse.ArgumentParser(prog='mat2raw')
    p.add_argument('input'); p.add_argument('output', nargs='?'); p.add_argument('--overwrite', action='store_true')
    a = p.parse_args()
    from pathlib import Path
    return main(['convert', a.input, a.output or str(Path(a.input).with_suffix('.raw'))] + (['--overwrite'] if a.overwrite else []))
