"""Version and license documents available in source and standalone builds."""
from importlib import metadata
from pathlib import Path


def version():
    try: return metadata.version('opencaliper')
    except metadata.PackageNotFoundError: return 'development'


def license_documents():
    """Read project notices and bundled dependency license text without network access."""
    documents = {}
    root = Path(__file__).resolve().parents[1]
    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        path = root/name
        if path.is_file(): documents['OpenCaliper / '+name] = path.read_text(encoding='utf-8', errors='replace')
    for distribution in metadata.distributions():
        package = distribution.metadata.get('Name', 'Dependency')
        for file in distribution.files or []:
            parts = [part.lower() for part in file.parts]
            if not any(part.endswith('.dist-info') for part in parts): continue
            if not ('licenses' in parts or file.name.lower().startswith(('license','copying','notice'))): continue
            path = distribution.locate_file(file)
            if path.is_file():
                try: documents[f'{package} / {file.as_posix()}'] = path.read_text(encoding='utf-8', errors='replace')
                except OSError: pass
    return dict(sorted(documents.items()))
