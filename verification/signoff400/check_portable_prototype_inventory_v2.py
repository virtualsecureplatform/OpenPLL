"""Verify a staged prototype package after relocation, without source-tree imports.

This checks portable bytes and provenance only. Native replay and integration
qualification remain separate gates.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('portable relative path required')
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or str(p) != name or not p.parts:
        raise ValueError('normalized relative path required')
    return p


def check(package, receipt_sha256):
    package = package.resolve(strict=True)
    if not package.is_dir():
        raise ValueError('package directory required')
    # Do not follow links into the original workspace, including control files.
    if any(p.is_symlink() for p in package.rglob('*')):
        raise ValueError('package contains a symbolic link')
    inventory = json.loads((package/'inventory.json').read_text())
    if digest(package/'assessment.json') != receipt_sha256:
        raise ValueError('staging receipt differs from trusted digest')
    assessment = json.loads((package/'assessment.json').read_text())
    manifest = json.loads((package/'manifest.input.json').read_text())
    if not assessment.get('package_staged') or not assessment.get('qualification_prerequisites_passed'):
        raise ValueError('qualified staging receipt required')
    if assessment['candidate'] != manifest['candidate']:
        raise ValueError('candidate identity differs between receipt and manifest')
    requirements = digest(package/'requirements.json')
    if assessment['profile_sha256'] != requirements:
        raise ValueError('profile bytes changed')
    # Original absolute source paths are provenance identifiers; they are never
    # opened. Rebase the staged receipt through its unique inventory.json path.
    receipt = assessment['artifacts']
    roots = [str(Path(p).parent) for p in receipt if Path(p).name == 'inventory.json']
    if len(roots) != 1:
        raise ValueError('unique staged inventory identity required')
    old_root = PurePosixPath(roots[0])
    rebased = {}
    for old, sha in receipt.items():
        try:
            name = str(PurePosixPath(old).relative_to(old_root))
        except ValueError as error:
            raise ValueError('staged artifact is outside package root') from error
        relative(name)
        if name in rebased:
            raise ValueError('duplicate staged artifact')
        rebased[name] = sha
    actual = {str(p.relative_to(package)) for p in package.rglob('*') if p.is_file()}
    if actual != set(rebased) | {'assessment.json'}:
        raise ValueError('missing or unlisted package file')
    for name, sha in rebased.items():
        if digest(package/name) != sha:
            raise ValueError('staged artifact bytes changed: '+name)
    expected = {}
    for role, entries in manifest['handoff_artifacts'].items():
        for entry in entries:
            name = str(relative(entry['destination']))
            if name in expected:
                raise ValueError('duplicate manifest destination')
            expected[name] = (role, entry['source'])
    observed = {}
    for entry in inventory:
        name = str(relative(entry['path']))
        if name in observed:
            raise ValueError('duplicate inventory destination')
        if rebased.get(name) != entry['sha256']:
            raise ValueError('inventory and staging receipt disagree')
        observed[name] = (entry['role'], entry['source'])
    if observed != expected:
        raise ValueError('inventory and handoff manifest disagree')
    for role, field in [('rtl', 'source_sha256'), ('gds', 'physical_sha256')]:
        exported = {entry['source']: entry['sha256'] for entry in inventory if entry['role'] == role}
        required = assessment['candidate'].get(field)
        if not isinstance(required, dict) or not required or any(exported.get(name) != sha for name, sha in required.items()):
            raise ValueError('incomplete candidate '+role+' inventory')
    return dict(profile_sha256=requirements, candidate=assessment['candidate'],
                relocated_inventory_verified=True, candidate_rtl_complete=True,
                candidate_physical_complete=True, source_paths_opened=False,
                files_verified=len(rebased), clean_environment_replay_complete=False,
                representative_native_replay_complete=False,
                integration_contract_verified=False, release_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--receipt-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.package, args.receipt_sha256), indent=2))
