#!/usr/bin/env python3
"""Freeze a solver-only DCO trial; start no simulation and stop no process."""
from datetime import datetime,timezone
import json
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
prior=base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
manifest=json.loads((prior/'input_manifest.json').read_text());owner=json.loads((prior/'owner.json').read_text())
proof=base/'bounded_reuse_native_controls_audit_002/assessment.json';audit=json.loads(proof.read_text());assert audit['completed_native_control_audit_passed']
controls=base/'bounded_reuse_native_controls_002/assessment.json';control=json.loads(controls.read_text());assert control['native_adapter_controls_passed']
for p,sha in {**control['input_sha256'],**control['artifacts']}.items():assert digest(Path(p))==sha,p
build=base/'wire_preconditioned_Xyce_bounded_reuse_001/recovered_build_assessment.json';built=json.loads(build.read_text());binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
probe=base/'native_bounded_reuse_probe_checks_001/assessment.json';assert json.loads(probe.read_text())['all_original_equation_residual_checks_passed']
out=base/'DCO_bounded_reuse_trial_prepared_001';out.mkdir(exist_ok=False)
deck=out/'point.cir';deck.write_bytes((prior/'point.cir').read_bytes())
pins=dict(manifest['input_sha256'])
for p in (Path(__file__).resolve(),proof,controls,build,binary,probe,prior/'input_manifest.json',prior/'owner.json',prior/'point.cir',deck,
          Path(__file__).with_name('run_DCO_bounded_reuse_trial.py'),Path(__file__).with_name('check_bounded_reuse_DCO_map.py')):
    pins[str(p)]=digest(p)
for p,sha in pins.items():assert digest(Path(p))==sha,p
save(out/'plan.json',dict(prepared_utc=datetime.now(timezone.utc).isoformat(),source_point=str(prior),deadline_uptime=owner['deadline_uptime'],
    budget_restarted=False,binary=str(binary),binary_sha256=built['binary_sha256'],parameters=manifest['parameters'],input_sha256=pins,
    integration_method='GEAR',circuit_and_integration_byte_identical=True,numerical_tolerances_unchanged=True,
    solver_change='Projected previous solution with at most eight same-alpha factor reuses; stale solve capped at20 iterations before fresh-factor fallback',
    original_solver_point_must_be_terminal=True,full_native_variable_map_gate_required=True,
    native_started=False,native_DCO_speedup_proven=False,release_qualified=False,adopted=False))
print('Prepared byte-identical Gear circuit; inherited original experiment deadline')
