"""Build a single-file Linux application using the current Linux Python."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist')
    parser.add_argument('--work', type=Path, default=ROOT/'build/linux')
    args = parser.parse_args(argv)
    if sys.platform != 'linux':
        parser.error('Run this builder with Linux Python on the target architecture.')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--distpath', str(args.output.resolve()), '--workpath', str(args.work.resolve()),
               str(ROOT/'bundle/OpenCaliper.spec')]
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Linux build failed: {exc}', file=sys.stderr)
        return 1
    print(f'Built {args.output.resolve()/"OpenCaliper"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
