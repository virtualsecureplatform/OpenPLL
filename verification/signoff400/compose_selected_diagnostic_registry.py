"""Bind an existing diagnostic registry to a matching publication composition."""
import argparse
import copy
import json
from pathlib import Path
from common_v3 import save,sha,verify
from selected_model_registry import validate,fingerprint


def compose(source,composition,output):
    if output.exists():raise FileExistsError(output)
    registry = copy.deepcopy(validate(json.loads(source.read_text())))
    receipt = composition/'assessment.json'
    c = json.loads(receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    raw = Path(registry['interface']['detector_rtl'])
    detector = composition/'detector.v'
    if c['operating_point'] != registry['analog']['operating_point']:
        raise ValueError('composition and calibration operating points differ')
    if c['input_sha256'].get(str(raw)) != sha(raw):
        raise ValueError('composition must derive from the registered raw detector')
    if c['artifacts'].get(str(detector)) != sha(detector) or c['release_ready'] is not False:
        raise ValueError('explicit pinned diagnostic composition required')
    identity = registry['interface']
    identity['input_sha256'].update(c['input_sha256'])
    identity['input_sha256'].update({str(receipt):sha(receipt),str(detector):sha(detector)})
    identity.update(detector_rtl=str(detector),diagnostic_publication_composition=str(receipt),native_interface_qualified=False)
    registry['interface_key'] = fingerprint(identity)
    validate(registry)
    save(output,registry)
    return registry


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source','composition','output'):p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args();compose(a.source.resolve(),a.composition.resolve(),a.output.resolve())
