# Build natively: python scripts/build_windows.py or scripts/build_linux.py
from pathlib import Path
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
# Readers/exporters are selected by importlib; Analysis cannot discover them all.
hidden = collect_submodules('opencaliper.converterscripts')
data = collect_data_files('opencaliper')
data += [(str(root/name), '.') for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md')]
data += copy_metadata('opencaliper', recursive=True)

a = Analysis(
    [str(root/'scripts/frozen_entry.py')],
    pathex=[str(root)],
    binaries=[], datas=data, hiddenimports=hidden,
    hooksconfig={'matplotlib': {'backends': ['Agg']}},
    excludes=['PyQt5','PyQt6','PySide2','tkinter','pytest','IPython'],
    noarchive=False,
)
# Windows 10+ supplies these API-set/UCRT libraries. Never package Wine's
# compatibility stubs (or copies of operating-system runtime DLLs).
system_dir = str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'System32').lower()
def app_binary(entry):
    name = Path(entry[0]).name.lower()
    if name.startswith('api-ms-win-') or name == 'ucrtbase.dll': return False
    if str(Path(entry[1]).parent).lower() == system_dir and name.startswith('icu'): return False
    return True
a.binaries = [entry for entry in a.binaries if app_binary(entry)]
pyz = PYZ(a.pure)
# Passing binaries/data directly to EXE creates one file (no COLLECT directory).
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='OpenCaliper', debug=False, strip=False, upx=False,
    console=False,
    icon=str(root/'opencaliper/assets/opencaliper.png') if sys.platform == 'win32' else None,
    disable_windowed_traceback=False,
)
