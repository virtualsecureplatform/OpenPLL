#!/usr/bin/env python3
"""Prepare a method-only fallback; leave the active TRAP point untouched."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    prior = base / 'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_002'
    manifest = json.loads((prior / 'input_manifest.json').read_text())
    owner = json.loads((prior / 'owner.json').read_text())
    controls = base / 'wire_preconditioned_native_controls_004/assessment.json'
    audit = base / 'wire_preconditioned_native_controls_checks_002/assessment.json'
    comparison = base / 'completed_stiff_integration_comparison_001/assessment.json'
    assert json.loads(controls.read_text())['native_adapter_controls_passed']
    deadline = owner['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    source = prior / 'point.cir'
    pins = dict(manifest['input_sha256'])
    for path in (Path(__file__).resolve(), source, prior / 'input_manifest.json',
                 prior / 'owner.json', controls, audit, comparison):
        pins[str(path)] = digest(path)
    for path, sha in pins.items():
        assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        assert digest(Path(path)) == sha, path
    original = source.read_text()
    trap_option = '.options TIMEINT RELTOL=1e-05 ABSTOL=1e-09'
    gear_option = trap_option+' METHOD=GEAR'
    assert original.count(trap_option) == 1 and 'METHOD=' not in original.upper()
    changed = original.replace(trap_option, gear_option, 1)
    assert changed.replace(gear_option, trap_option, 1) == original
    out = base / 'DCO_gear_method_fallback_prepared_001'
    out.mkdir(exist_ok=False)
    deck = out / 'point.cir'
    deck.write_text(changed)
    pins[str(deck)] = digest(deck)
    save(out / 'plan.json', dict(input_sha256=pins,
        prepared_utc=datetime.now(timezone.utc).isoformat(), source_point=str(prior),
        inherited_owner=str(prior / 'owner.json'), deadline_uptime=deadline,
        budget_restarted=False, circuit_and_initial_bias_unchanged=True,
        integration_method_only_change='default TRAP to GEAR',
        parameters=manifest['parameters'], native_execution_started=False,
        simultaneous_large_DCO_runs_allowed=False, automatic_identical_retry=False,
        activate_only_after_documented_runtime_handoff_decision=True,
        source_model_and_frequency_convergence_qualified=False,
        method_frequency_convergence_qualified=False, runtime_model_eligible=False,
        release_qualified=False, adopted=False,
        scope='Prepared fallback for an observed runtime problem; small-fixture Gear '
              'controls do not prove DCO frequency accuracy. The running TRAP point is unchanged.'))
    print(json.dumps(dict(output=str(out), deadline_uptime=deadline, native_started=False)))


if __name__ == '__main__':
    main()
