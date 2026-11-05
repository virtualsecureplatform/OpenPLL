"""Stage a pinned prototype handoff; clean replay remains a separate release gate."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from audit_prototype_v3 import audit
from common_v3 import PROFILE, save, sha, verify

ROLES = {'gds', 'lef', 'netlist', 'powered_netlist', 'parasitics', 'timing',
         'constraints', 'calibration', 'models', 'integration', 'rtl', 'replay', 'toolchain'}


def destination(name):
    if not isinstance(name, str) or '\\' in name:
        raise ValueError('portable POSIX destination required')
    path = PurePosixPath(name)
    if not name or not path.parts or path.is_absolute() or '..' in path.parts or str(path) != name:
        raise ValueError('normalized relative package destination required')
    if path.parts[0] in {'assessment.json', 'manifest.input.json', 'requirements.json', 'inventory.json'}:
        raise ValueError('reserved package destination')
    return name


def add_pins(pins, extra):
    for name, digest in extra.items():
        if name in pins and pins[name] != digest:
            raise ValueError('conflicting qualification identity: '+name)
        pins[name] = digest


def run(manifest_path, output):
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    result = audit(manifest)
    prerequisites = set(result['gates'])-{'reproducible_handoff'}
    if result['identity_failures'] or any(result['gates'][g]['status'] != 'pass' for g in prerequisites):
        raise ValueError('package blocked: prototype qualification prerequisites remain open')
    artifacts = manifest['handoff_artifacts']
    if set(artifacts) != ROLES or any(not entries for entries in artifacts.values()):
        raise ValueError('complete physical, source, replay and toolchain roles required')
    candidate = manifest['candidate']
    qualified = {}
    add_pins(qualified, candidate['source_sha256'])
    add_pins(qualified, candidate['physical_sha256'])
    evidence = {}
    for gate in prerequisites:
        for entry in manifest['evidence'][gate]:
            path = Path(entry['path'])
            if sha(path) != entry['sha256']:
                raise ValueError('qualification receipt changed')
            add_pins(evidence, {str(path): entry['sha256']})
            receipt = json.loads(path.read_text())
            add_pins(qualified, receipt['input_sha256'])
            add_pins(qualified, receipt['artifacts'])
    inventory = []
    names = set()
    for role in sorted(artifacts):
        for entry in artifacts[role]:
            name = destination(entry['destination'])
            if name in names:
                raise ValueError('duplicate package destination: '+name)
            names.add(name)
            source = Path(entry['source'])
            digest = sha(source)
            if qualified.get(str(source)) != digest:
                raise ValueError('handoff artifact lacks qualifying provenance: '+str(source))
            inventory.append(dict(role=role, path=name, sha256=digest, source=str(source)))
    # Reject file/directory collisions before creating any package output.
    for name in names:
        if any(str(p) in names for p in PurePosixPath(name).parents if str(p) != '.'):
            raise ValueError('package file/directory collision')
    verify(qualified)
    if sha(manifest_path) != hashlib.sha256(raw).hexdigest():
        raise ValueError('manifest changed during package preflight')
    output.mkdir(parents=True, exist_ok=False)
    (output/'manifest.input.json').write_bytes(raw)
    shutil.copyfile(PROFILE, output/'requirements.json')
    for entry in inventory:
        target = output/entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(entry['source'], target)
        if sha(target) != entry['sha256']:
            raise ValueError('artifact changed during package copy')
    save(output/'inventory.json', inventory)
    verify(qualified)
    save(output/'assessment.json', dict(
         input_sha256={**qualified, **evidence, str(manifest_path): hashlib.sha256(raw).hexdigest(),
                       str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
         artifacts={str(p): sha(p) for p in output.rglob('*') if p.is_file()},
         profile_sha256=sha(PROFILE), candidate=candidate, package_staged=True,
         qualification_prerequisites_passed=True, source_bytes_rewritten=False,
         portable_paths_verified=False, clean_environment_replay_complete=False,
         representative_native_replay_complete=False, integration_contract_verified=False,
         reproducible_handoff_qualified=False, release_ready=False, production_qualified=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    run(a.manifest.resolve(), a.output.resolve())
