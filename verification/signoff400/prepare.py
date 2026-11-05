#!/usr/bin/env python3
"""Create a fresh 15-PVT campaign; imported geometry remains scoped evidence."""
import argparse
import json
from pathlib import Path
from common import ROOT, PROFILE, cases, save, sha, source_pins
from audit import audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    historical=ROOT/'build/timing400/prototype_001/filled_closure_005/assessment.json'
    prior=ROOT/'build/timing400/prototype_001/status.json'
    geometry=json.loads(prior.read_text())['filled_geometry']
    gds=Path(geometry['gds'])
    if sha(gds)!=geometry['gds_sha256'] or sha(historical)!=geometry['assessment_sha256']:
        raise ValueError('retained assembled geometry identity mismatch')
    manifest=dict(profile=str(PROFILE),profile_sha256=sha(PROFILE),
         candidate=dict(source_sha256=source_pins(),physical_sha256={str(gds):sha(gds)}),
         evidence={},handoff_artifacts={},
         imported_geometry=dict(path=str(historical),sha256=sha(historical),
             geometry_checks_pass=geometry['geometry_checks_pass'],
             applicability='matching geometry only; electrical and temperature qualification remain open'),
         release_qualified=False)
    save(out/'manifest.json',manifest)
    save(out/'functional_matrix.json',dict(profile_sha256=sha(PROFILE),cases=cases(),release_qualified=False))
    save(out/'status.json',audit(manifest))
    print(out/'manifest.json')


if __name__=='__main__':main()
