"""Build the single-file Windows application with the current Windows Python.

Install python -m pip install -e ".[windows-build]" first. Cross-compiling with a
Linux Python is not supported. An isolated Windows Python under Wine can build
an additional test artifact; release verification should use native Windows.
"""
import argparse
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build_command(output, work):
    return [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', str(Path(output).resolve()), '--workpath', str(Path(work).resolve()),
            str(ROOT/'bundle/OpenCaliper.spec')]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist')
    parser.add_argument('--work', type=Path, default=ROOT/'build/windows')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        parser.error('Run this builder with Windows Python. Use the Windows executable GitHub Actions workflow from Linux.')
    if platform.architecture()[0] != '64bit':
        parser.error('Use 64-bit Windows Python to build the Windows x64 release.')
    try:
        subprocess.run(build_command(args.output, args.work), cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Windows build failed: {exc}', file=sys.stderr)
        return 1
    print(f'Built {args.output.resolve()/"OpenCaliper.exe"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
