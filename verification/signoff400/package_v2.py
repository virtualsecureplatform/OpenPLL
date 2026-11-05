#!/usr/bin/env python3
"""Package a hard macro only after all six physical/functional gates pass."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from common_v2 import PROFILE, save, sha, verify
from audit_v2 import audit

ROLES={'gds','lef','netlist','powered_netlist','parasitics','timing','constraints',
       'calibration','models','integration'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();manifest_bytes=a.manifest.read_bytes();manifest=json.loads(manifest_bytes)
    report=audit(manifest,require_handoff=False)
    if not report['prerequisite_gates_passed']:
        raise ValueError('package blocked: mandatory qualification gates remain open')
    artifacts=manifest['handoff_artifacts']
    if set(artifacts)!=ROLES:raise ValueError('all ten hard-macro artifact roles are required')
    qualified=dict(manifest['candidate']['physical_sha256'])
    qualified.update(manifest['candidate']['source_sha256'])
    evidence_paths={}
    for entries in manifest['evidence'].values():
        for entry in entries:
            evidence_paths[entry['path']]=entry['sha256']
            r=json.loads(Path(entry['path']).read_text())
            qualified.update(r['input_sha256']);qualified.update(r['artifacts'])
    for role,paths in artifacts.items():
        if not paths:raise ValueError('empty artifact role: '+role)
        for path in paths:
            if qualified.get(path)!=sha(path):raise ValueError('artifact not pinned by qualifying evidence: '+path)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    # The campaign later gains this package's receipt. Pin a frozen copy rather
    # than making the receipt invalidate itself when that link is added.
    snapshot=out/'manifest.input.json';snapshot.write_bytes(manifest_bytes)
    if sha(a.manifest)!=hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('campaign manifest changed during packaging')
    copied={}
    copied[str(snapshot)]=sha(snapshot)
    for role,paths in artifacts.items():
        directory=out/role;directory.mkdir()
        for i,path in enumerate(paths):
            target=directory/f'{i:03d}_{Path(path).name}'
            shutil.copyfile(path,target);copied[str(target)]=sha(target)
            if copied[str(target)]!=qualified[path]:raise ValueError('package copy mismatch')
    evidence=out/'evidence';evidence.mkdir()
    for i,(path,digest) in enumerate(evidence_paths.items()):
        target=evidence/f'{i:03d}.json';shutil.copyfile(path,target)
        if sha(target)!=digest:raise ValueError('evidence changed during packaging')
        copied[str(target)]=digest
    shutil.copyfile(PROFILE,out/'requirements.json');copied[str(out/'requirements.json')]=sha(PROFILE)
    verify(qualified)
    report.update(reproducible_handoff_qualified=True,macro_handoff_qualified=True,release_qualified=True,
                  input_sha256={str(snapshot):sha(snapshot),**qualified,**evidence_paths},artifacts=copied)
    save(out/'assessment.json',report)
    print(out/'assessment.json')


if __name__=='__main__':main()
