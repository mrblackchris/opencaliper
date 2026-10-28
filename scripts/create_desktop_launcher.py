"""Create a user-local Linux launcher so desktops can associate the taskbar logo.

Run this with the Python interpreter used for OpenCaliper. No files are changed
until this script is explicitly run. Existing launchers require --overwrite.
"""
import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def desktop_value(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def exec_argument(value):
    value = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\'+char)
    return '"'+value+'"'


def create_launcher(destination, interpreter=sys.executable, overwrite=False):
    """Write a desktop entry bound to this checkout and the selected Python."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ' '.join([exec_argument(interpreter), exec_argument(ROOT/'run_opencaliper.py'), '%F'])
    content = ('[Desktop Entry]\nType=Application\nName=OpenCaliper\n'
               'Comment=View and analyze measurement signals\n'
               f'Exec={desktop_value(command)}\n'
               f'Icon={desktop_value(ROOT/"opencaliper/assets/opencaliper.png")}\n'
               'Terminal=false\nCategories=Science;\nStartupWMClass=opencaliper\n')
    with destination.open('w' if overwrite else 'x', encoding='utf-8') as output:
        output.write(content)
    return destination


def main(argv=None):
    data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=data_home/'applications/opencaliper.desktop')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    try: print(create_launcher(args.output, overwrite=args.overwrite))
    except OSError as exc:
        print(f'Could not create desktop launcher: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
