#!/usr/bin/env python3
"""Retain one startup period comparison; establish no frequency error bound."""
import json
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
from compare_bounded_reuse_DCO_cycles import parse_prefix,edges
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
point=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
prior=base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
reference_path=base/'retained_Gear_before_bounded_reuse_audit_001/assessment.json'
reference=json.loads(reference_path.read_text());assert reference['controlled_interruption_verified']
for p,sha in reference['input_sha256'].items():assert digest(Path(p))==sha,p
launch=json.loads((point/'launch.json').read_text());identity=process(launch['pid'])
assert identity['live'] and identity['argv']==launch['command']
assert (point/'point.cir').read_bytes()==(prior/'point.cir').read_bytes()
rows,raw=parse_prefix(Path(str(point/'point.cir')+'.prn').read_bytes());found=edges(rows)
assert len(found['falling'])>=2
old_edges=reference['post_reset_edges_s']['fall'];new_edges=found['falling']
old=old_edges[1]-old_edges[0];new=new_edges[1]-new_edges[0]
out=base/'bounded_reuse_DCO_first_period_review_001';out.mkdir(exist_ok=False)
snapshot=out/'candidate_waveform_prefix.prn';snapshot.write_bytes(raw)
pins={str(p):digest(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('compare_bounded_reuse_DCO_cycles.py'),
    reference_path,point/'launch.json',point/'point.cir',prior/'point.cir',snapshot)}
save(out/'assessment.json',dict(input_sha256=pins,source_native_identity=identity,
    direction='falling',threshold_V=.9,reference_first_period_s=old,candidate_first_period_s=new,
    reference_edges_s=old_edges[:2],candidate_edges_s=new_edges[:2],
    frequency_difference_Hz=1/new-1/old,frequency_difference_ppm_of_reference=(old/new-1)*1e6,
    signed_difference_s=new-old,absolute_difference_s=abs(new-old),candidate_last_sample_s=rows[-1][0],
    interpolated_startup_period_comparison_only=True,acceptance_threshold_selected=False,
    timestamp_agreement_is_not_physical_accuracy_bound=True,complete_periods_compared=1,
    native_started_stopped_or_retried=False,settled_frequency_qualified=False,numerical_domain_qualified=False,
    release_qualified=False,adopted=False))
print(json.dumps(dict(reference_first_falling_period_ns=old*1e9,candidate_first_falling_period_ns=new*1e9,frequency_difference_ppm_of_reference=(old/new-1)*1e6,
    signed_difference_s=new-old,release_qualified=False)))
