#!/usr/bin/env python3
"""Corrected audit of completed native cases; never repeats CAD runs."""
import argparse
import json
from pathlib import Path
import tarfile
import time
from common import save, sha
from check_origin_guard_label_cases_v2 import graph
from check_magic_origin_guard_v3 import outside_origins, matrix, devices


def recipe(template, case, corner):
    text = template.replace('extract style ngspice()', 'extract style '+dict(
        nom='ngspice()', min='ngspice(lrlc)', max='ngspice(hrhc)')[corner])
    if case == 'contained_y':
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.94um 1.28um 5um 1.32um')
    elif case == 'boundary_y':
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.94um 1.33um 5um 2um')
    elif case == 'span_x':
        text = text.replace('box values 4.94um 1.33um 5um 6um', 'box values 5um 1.26um 9um 1.32um')
        text = text.replace('box values 4.94um 1.325um 5um 2um', 'box values 4.995um 1.27um 6um 1.31um')
        text = text.replace('box values 4.95um 5.5um 4.99um 5.8um', 'box values 8.5um 1.27um 8.8um 1.31um')
    return text


def run(source, output):
    source, out = Path(source).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    save(out/'status.json', dict(state='auditing_retained_native_cases_corrected_parser', release_qualified=False))
    try:
        manifest = source/'input_manifest.json'
        m = json.loads(manifest.read_text())
        scratch = Path(m['retained_local_scratch'])
        pins = dict(m['input_sha256'])
        for p in (manifest, source/'status.json', Path(__file__).resolve(),
                  Path(__file__).with_name('check_origin_guard_label_cases_v2.py')):
            pins[str(p)] = sha(p)
        for p, h in pins.items():
            if sha(p) != h:
                raise ValueError('retained native input changed: '+p)
        templates = [Path(p) for p in pins if p.endswith('/native_label_breakpoint_reproducer_003/control.tcl')]
        if len(templates) != 1:
            raise ValueError('unique pinned baseline recipe required')
        template = templates[0].read_text()
        results, artifacts, raw_pins = [], {}, {}
        for corner in ('min', 'nom', 'max'):
            for case in ('span_y', 'contained_y', 'boundary_y', 'span_x'):
                if time.monotonic()-start >= 43200:
                    raise TimeoutError('corrected audit deadline')
                root = scratch/(corner+'_'+case)
                for path in root.rglob('*'):
                    if path.is_file():
                        raw_pins[str(path)] = sha(path)
                for tool in ('original', 'candidate'):
                    target = root/tool
                    if (target/'control.tcl').read_text() != recipe(template, case, corner):
                        raise ValueError('native case recipe mismatch')
                    if 'LABEL_BREAKPOINT_DRIVEN_CONTROL_COMPLETE' not in (target/'native.log').read_text():
                        raise ValueError('native case incomplete; no retry authorized by this auditor')
                a, b = root/'original', root/'candidate'
                old, labels = outside_origins(a)
                new, new_labels = outside_origins(b)
                if len(old) != (2 if case in ('span_y', 'span_x') else 0) or new:
                    raise ValueError('outside origin regression')
                if not new_labels or {tuple(r['point']) for r in labels} != {tuple(r['point']) for r in new_labels}:
                    raise ValueError('original label drivepoint changed')
                if matrix(a/'before.spice') != matrix(b/'before.spice') or devices(a/'LABEL_SPAN_DRIVEN.ext') != devices(b/'LABEL_SPAN_DRIVEN.ext'):
                    raise ValueError('native pre-R C or device regression')
                unchanged = case in ('contained_y', 'boundary_y')
                if unchanged and graph(a) != graph(b):
                    raise ValueError('valid/boundary native R graph regression')
                results.append(dict(case=case, RC_rule_corner=corner, original_outside_origins=len(old),
                    candidate_outside_origins=len(new), original_drivepoints_preserved=True,
                    pre_R_C_and_devices_unchanged=True, unchanged_R_graph_checked=unchanged))
                archive = out/(root.name+'.tar')
                with tarfile.open(archive, 'x') as stream:
                    stream.add(root, arcname=root.name)
                # Verify archive payload hashes against the exact retained files.
                with tarfile.open(archive) as stream:
                    import hashlib
                    for member in stream.getmembers():
                        if member.isfile():
                            original = scratch/member.name
                            if hashlib.sha256(stream.extractfile(member).read()).hexdigest() != raw_pins[str(original)]:
                                raise ValueError('published native archive bytes differ')
                artifacts[str(archive)] = sha(archive)
        for p, h in {**pins, **raw_pins}.items():
            if sha(p) != h:
                raise ValueError('native case changed during corrected audit: '+p)
        save(out/'cases.json', results)
        artifacts[str(out/'cases.json')] = sha(out/'cases.json')
        result = dict(input_sha256=pins, retained_raw_file_sha256=raw_pins, artifacts=artifacts,
            source_native_runs_repeated=False, native_runs=24, case_pairs=len(results),
            native_R_graph_unchanged_case_pairs=sum(r['unchanged_R_graph_checked'] for r in results),
            original_outside_origins=sum(r['original_outside_origins'] for r in results),
            candidate_outside_origins=sum(r['candidate_outside_origins'] for r in results),
            label_corner_native_controls_passed=True, full_native_regression_passed=False,
            full_layout_outside_geometry_resolved=False, resistance_PVT_qualified=False,
            physical_RC_qualified=False, release_qualified=False, adopted=False, elapsed_s=time.monotonic()-start)
        save(out/'assessment.json', result)
        save(out/'status.json', dict(state='retained_native_label_cases_passed_full_qualification_pending', release_qualified=False))
        return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.source, a.output)))
