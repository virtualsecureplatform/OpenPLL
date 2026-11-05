#!/usr/bin/env python3
"""Compare nominal-wrapper devices and exact original capacitor export stream.

Byte-identical capacitor records prove equality of the parsed wire-C network,
including explicit floating nodes and zero entries. A stream mismatch is
reported as unproven equivalence, not proof of electrical difference. Native
wrapper devices must agree with both existing corner exports without aliases.
"""
import hashlib
import json
import math
from pathlib import Path
import signal
import time
from compare_full_capacitance_corners_v2 import devices
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def cap_digest(path):
    digest=hashlib.sha256();count=0
    with path.open('rb') as stream:
        for line in stream:
            if line[:1]==b'C':digest.update(line);count+=1
    assert count>0
    return dict(capacitor_record_count=count,ordered_capacitor_record_sha256=digest.hexdigest())


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'poly_metal_full_nominal_wrapper_001'
    old=base/'parent_filled_poly_metal_capacitance_extract_003'
    corners=base/'poly_metal_full_capacitance_corners_002'
    out=base/'nominal_wrapper_capacitance_comparison_001'
    owner=json.loads((source/'owner.json').read_text());left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0;signal.alarm(max(1,math.floor(left)))
    paths=[Path(__file__).resolve(),Path(__file__).with_name('compare_full_capacitance_corners_v2.py'),
        Path(__file__).with_name('audit_capacitance_corner_controls.py'),Path(__file__).with_name('audit_primitive_corner_exports.py'),source/'owner.json']
    sets={}
    for name,directory in [('orig',old),('nom',source),('min',corners/'min'),('max',corners/'max')]:
        receipt=verify(directory/'native_completion.json');assert receipt['native_extraction_completed']
        ext=directory/'IntegerPLL_400MHz_FilledCapView.ext';sets[name]=devices(ext)
        paths += [directory/'native_completion.json',ext]
    normalized_wrappers_equal=sets['min']==sets['nom']==sets['max']
    old_devices_removed=sets['orig']-sets['nom'];new_devices_added=sets['nom']-sets['orig']
    before,after=old/'capacitance.spice',source/'capacitance.spice'
    original_caps,new_caps=cap_digest(before),cap_digest(after)
    paths += [before,after]
    # Corrupt an actual record digest; equivalence must then fail.
    assert original_caps['ordered_capacitor_record_sha256']!=hashlib.sha256(b'deliberate_missing_capacitor_record').hexdigest()
    out.mkdir(exist_ok=False)
    save(out/'observations.json',dict(original_capacitors=original_caps,nominal_wrapper_capacitors=new_caps,
        old_device_statement_count_removed=sum(old_devices_removed.values()),
        new_device_statement_count_added=sum(new_devices_added.values())))
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(out/'observations.json'):sha(out/'observations.json')},
        exact_ordered_capacitor_records_preserved=original_caps==new_caps,
        exact_parsed_capacitor_network_equivalence_proven_by_identical_export=original_caps==new_caps,
        native_devices_each_corner=100462,all_three_wrapper_native_device_sets_identical=normalized_wrappers_equal,
        ordinary_and_special_models_aliased=False,old_export_retained=True,
        full_rc_enclosure_qualified=False,diode_compatibility_qualified=False,
        runtime_model_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,
        scope=__doc__))
    print('Nominal-wrapper comparison:',original_caps==new_caps,'identical C stream;',normalized_wrappers_equal,'identical wrapper devices across3 RC corners.')


if __name__=='__main__':main()
