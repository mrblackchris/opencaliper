"""Selectable converter scripts and paired MAT conversion, independent of Qt."""
import ast
from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
from .formats import FORMATS
from .pairedexport import write


@dataclass(frozen=True)
class Converter:
    """A built-in module or explicitly selected Python reader script."""
    name: str
    module: str = ''
    script: Path | None = None


def converter_folder():
    """Source adapters in a checkout; editable sibling folder beside a frozen EXE."""
    if getattr(sys, 'frozen', False): return Path(sys.executable).resolve().parent/'converterscripts'
    return Path(__file__).resolve().parent


def discover(folder=None):
    """List built-ins plus scripts defining read(path), without executing scripts."""
    found = [Converter('Automatic format detection')]
    seen = set()
    for fmt in FORMATS.values():
        if fmt.reader and fmt.reader not in seen:
            found.append(Converter(fmt.name, module=fmt.reader)); seen.add(fmt.reader)
    # This schema-specific CSV adapter is also available independently of detection.
    found.append(Converter('EMC receiver CSV (QPK / PK+ / AVG)', module='emccsvconvert'))
    for path in sorted(Path(folder or converter_folder()).glob('*.py')):
        if path.parent.resolve() == Path(__file__).parent.resolve() and path.stem in seen | {'emccsvconvert'}: continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            if not any(isinstance(node, ast.FunctionDef) and node.name == 'read' for node in tree.body): continue
            label, template = path.stem, False
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ('CONVERTER_NAME', 'CONVERTER_TEMPLATE'):
                            value = ast.literal_eval(node.value)
                            if target.id == 'CONVERTER_NAME' and isinstance(value, str): label = value
                            if target.id == 'CONVERTER_TEMPLATE': template = bool(value)
            if template: continue
        except (OSError, SyntaxError, ValueError, TypeError): continue
        found.append(Converter(label+' — '+path.name, script=path.resolve()))
    return found


def read_with(converter, source):
    """Run one reader. Custom scripts use the same Recording contract as built-ins."""
    from ..core import Recording
    if converter.script is None:
        if not converter.module:
            from .convert import load
            recording = load(source)
        else:
            module = importlib.import_module('.'+converter.module, __package__)
            recording = module.read(Path(source))
    else:
        script = converter.script.resolve()
        name = __package__+'._user_'+hashlib.sha256(str(script).encode()).hexdigest()[:16]
        spec = importlib.util.spec_from_file_location(name, script)
        if spec is None or spec.loader is None: raise ValueError('Cannot load converter script')
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(name)
        sys.modules[name] = module
        try:
            # Always read current source; rapid edits must not reuse stale .pyc files.
            exec(compile(script.read_bytes(), str(script), 'exec'), module.__dict__)
            if not callable(getattr(module, 'read', None)): raise ValueError('Converter script must define read(path) -> Recording')
            recording = module.read(Path(source))
        finally:
            if previous is None: sys.modules.pop(name, None)
            else: sys.modules[name] = previous
    if not isinstance(recording, Recording) or not recording.signals:
        raise ValueError('Converter read(path) must return a nonempty Recording')
    return recording


def output_path(source, folder=None):
    """Default beside input or in the chosen directory, with a distinct MAT suffix."""
    source = Path(source)
    return (Path(folder) if folder else source.parent)/(source.stem+'.opencaliper.mat')


def plan(sources, folder=None):
    """Refuse duplicate outputs and source replacement before starting conversions."""
    jobs = [(Path(source).resolve(), output_path(Path(source).resolve(), folder).resolve()) for source in sources]
    inputs = {os.path.normcase(str(source)) for source, _ in jobs}
    outputs = [os.path.normcase(str(target)) for _, target in jobs]
    if len(set(outputs)) != len(outputs): raise ValueError('Files would produce the same output name; rename them or convert beside each input')
    if any(target in inputs for target in outputs): raise ValueError('An output would replace a selected input file')
    return jobs


def convert_one(source, target, converter=None, overwrite=False):
    """Decode using a selected script and write paired MAT after successful parsing."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target: raise ValueError('Input and output paths must differ')
    if not source.is_file(): raise ValueError(f'Input file does not exist: {source}')
    if target.exists() and not overwrite: raise FileExistsError(target)
    recording = read_with(converter or Converter('Automatic format detection'), source)
    return write(recording, target, overwrite)


def create_template(destination):
    """Copy the contributor example without overwriting an existing script."""
    text = Path(__file__).with_name('converter_template.py').read_text(encoding='utf-8')
    # The copied script is immediately discoverable; edit its implementation next.
    text = text.replace('CONVERTER_TEMPLATE = True', 'CONVERTER_TEMPLATE = False')
    with Path(destination).open('x', encoding='utf-8') as file: file.write(text)
    return Path(destination)
