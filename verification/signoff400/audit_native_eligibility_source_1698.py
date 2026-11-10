"""Source-bound evidence for the native extraction coverage population."""
import json
import shlex
import time
from collections import Counter
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease


def run():
    base = ROOT / 'build/signoff400'
    source = base / 'selected_keeper_contact_corrected_C_1573'
    receipt = source / 'assessment.json'
    ext = source / 'IntegerPLL_400MHz_KeeperFlatC.ext'
    original = json.loads(receipt.read_text())
    if sha(ext) != original['artifacts'][str(ext)]:
        raise ValueError('checked complete source EXT changed')
    inventory_receipt = base / 'selected_reference_network_inventory_1690/assessment.json'
    inventory = json.loads(inventory_receipt.read_text())
    origins_receipt = base / 'selected_zero_junction_origins_1659/assessment.json'
    origins = json.loads(origins_receipt.read_text())
    if not origins['all_device_origins_bound'] or origins['input_sha256'].get(str(ext)) != sha(ext):
        raise ValueError('physical primitive binding to this source required')
    native = base / 'selected_magic_antenna_source_review_573/unpacked/magic-8.3.623/resis'
    paths = [receipt, ext, inventory_receipt, origins_receipt,
             native / 'ResReadExt.c', native / 'ResRex.c',
             ROOT / 'tools/magic_rcx/canonical_rc_conductors_v3.py',
             Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    out = base / 'selected_native_eligibility_source_1698'
    out.mkdir(exist_ok=False)
    with lease(1, 2, time.clock_gettime(time.CLOCK_BOOTTIME) + 300):
        counts, models = Counter(), Counter()
        selection, unsupported = [], []
        for line in ext.open():
            kind = line.partition(' ')[0].strip()
            counts[kind] += 1
            if kind == 'device':
                models[shlex.split(line)[2]] += 1
            elif kind == 'attr' and 'res:' in line:
                selection.append(line.rstrip())
            elif kind in ['fet', 'use', 'merge']:
                unsupported.append(line.rstrip())
        checks = dict(
            no_additional_attribute_selected_networks=not selection,
            no_legacy_or_hierarchical_device_records=not unsupported,
            all_primitives_physically_bound=sum(models.values()) == origins['device_count'] == 62338,
            no_gate_or_bulk_only_remainder=inventory['gate_only_networks'] == inventory['bulk_only_networks'] == 0,
            expected_active_population=inventory['required_device_and_port_networks'] == 19696,
            expected_external_interface=counts['port'] == 65)
        for name, digest in pins.items():
            if sha(Path(name)) != digest:
                raise ValueError('source eligibility input changed')
        save(out / 'assessment.json', dict(input_sha256=pins, checks=checks,
             source_selection_population_supported=all(checks.values()),
             record_counts=dict(counts), model_counts=dict(models),
             resistance_selection_attributes=selection, unsupported_records=unsupported,
             required_device_and_port_networks=inventory['required_device_and_port_networks'],
             capacitance_only_networks=inventory['capacitance_only_networks'],
             rule='native ResProcessNode requires device adjacency or a port/attribute drive point; all eligible output still must be verified',
             actual_native_output_coverage_verified=False,
             RC_export_fixed=False, release_ready=False))


if __name__ == '__main__':
    run()
