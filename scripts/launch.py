"""Set up the checkout's environment and launch the desktop application."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main(args=None):
    if sys.version_info < (3, 10):
        print('OpenCaliper requires Python 3.10 or newer.', file=sys.stderr)
        return 1
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    try:
        if not python.exists():
            print('Creating the local Python environment...', flush=True)
            venv.EnvBuilder(with_pip=True).create(environment)
        # Reinstall when project dependencies change, without contacting the
        # package index on every launch. Write the marker only after success.
        fingerprint = hashlib.sha256((ROOT / 'pyproject.toml').read_bytes()).hexdigest()
        marker = environment / '.opencaliper-setup'
        if not marker.exists() or marker.read_text().strip() != fingerprint:
            print('Installing OpenCaliper and its dependencies. First setup needs internet access...', flush=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(ROOT)], check=True)
            marker.write_text(fingerprint + '\n')
        return subprocess.call([str(python), '-m', 'opencaliper', 'gui',
                                *(sys.argv[1:] if args is None else args)])
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Could not start OpenCaliper: {exc}', file=sys.stderr)
        print('Check that Python includes pip and venv, and that dependencies can be downloaded.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
