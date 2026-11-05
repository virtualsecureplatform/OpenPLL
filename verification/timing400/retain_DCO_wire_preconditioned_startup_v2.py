#!/usr/bin/env python3
"""Independently retain a live startup prefix and audit its stock first step."""
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import json,math
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process

parser=argparse.ArgumentParser();parser.add_argument('--native-pid',type=int,required=True)
parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
point=base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_002'
state=json.loads((point/'status.json').read_text());assert state['native_pid']==args.native_pid
identity=process(args.native_pid)
assert identity['live'] and identity['argv'][-1]==str((point/'point.cir').resolve())
owner=json.loads((point/'owner.json').read_text());assert not owner['check_budget_restarted']
assert owner['deadline_uptime']==json.loads(Path(owner['inherited_check_owner']).read_text())['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME)<owner['deadline_uptime']
out=args.output.resolve();out.mkdir(exist_ok=False)
def prefix(source,target):
    text=source.read_text()
    if not text.endswith('\n'):text=text[:text.rfind('\n')+1]
    target.write_text(text);return text.splitlines()
wave=out/'retained_startup.prn';lines=prefix(point/'point.cir.prn',wave)
assert lines[0].split()==['Index','TIME','V(PLLOUT)','I(VVPWR)']
rows=[]
for line in lines[1:]:
    fields=line.split()
    if not fields:continue
    assert len(fields)==4 and int(fields[0])==len(rows)
    value=tuple(Decimal(v) for v in fields[1:]);assert all(v.is_finite() for v in value)
    assert not rows or value[0]>rows[-1][0];rows.append(value)
assert len(rows)>=3 and rows[0][0]==0 and abs(rows[1][0]-Decimal('10e-12'))<=Decimal('1e-24')
step=[b[0]-a[0] for a,b in zip(rows,rows[1:])]
assert max(step)<=Decimal('10e-12')*Decimal('1.000000000001')
comparison=json.loads((point/'first_step_comparison.json').read_text());assert comparison['first_step_equivalence_passed']
stock=point/'retained_stock_first_step.prn';candidate=point/'retained_experimental_first_step.prn'
assert digest(stock)==comparison['source_prefix_sha256'] and digest(candidate)==comparison['experimental_prefix_sha256']
a=[tuple(Decimal(x) for x in line.split()[1:]) for line in stock.read_text().splitlines()[1:]]
b=[tuple(Decimal(x) for x in line.split()[1:]) for line in candidate.read_text().splitlines()[1:]]
assert len(a)==len(b)==2 and [x[0] for x in a]==[x[0] for x in b]
dv=max(abs(x[1]-y[1]) for x,y in zip(a,b));di=max(abs(x[2]-y[2]) for x,y in zip(a,b))
assert dv<=Decimal('1e-6') and di<=Decimal('1e-10')
log=out/'retained_native.log';log_lines=prefix(point/'native.log',log)
solves=[]
for line in log_lines:
    if line.startswith('OpenPLL_wire_PC call='):
        values=dict(x.split('=',1) for x in line.split()[1:]);assert int(values['call'])==len(solves)+1
        result=dict(status=int(values['status']),error=float(values['scaled_true_relative_residual']),
            seconds=float(values['seconds']),alpha=float(values['alpha']))
        assert all(math.isfinite(result[k]) for k in ['error','seconds','alpha'])
        if result['status']==0:assert result['error']<=1e-12
        solves.append(result)
assert solves
again=process(args.native_pid);assert again['live'] and again['argv']==identity['argv']
inputs=[Path(__file__),point/'owner.json',point/'input_manifest.json',point/'first_step_comparison.json',stock,candidate]
save(out/'assessment.json',dict(independent_first_step_comparison_passed=True,
    maximum_voltage_difference_V=str(dv),maximum_supply_current_difference_A=str(di),
    source_native_identity=identity,observed_utc=datetime.now(timezone.utc).isoformat(),
    retained_samples=len(rows),simulation_time_s=str(rows[-1][0]),
    smallest_accepted_step_s=str(min(step)),largest_accepted_step_s=str(max(step)),
    last_accepted_step_s=str(step[-1]),last_measured_step_reached_configured_maximum=abs(step[-1]-Decimal('10e-12'))<Decimal('1e-22'),
    successful_linear_solves=sum(v['status']==0 for v in solves),rejected_linear_solves=sum(v['status']!=0 for v in solves),
    input_sha256={str(p.resolve()):digest(p) for p in inputs},
    artifacts={str(p):digest(p) for p in [wave,log]},original_check_deadline_unchanged=True,
    all_input_pins_revalidated=False,full_transient_completed=False,settled_frequency_qualified=False,
    full_DCO_speedup_qualified=False,release_qualified=False,adopted=False))
print(json.dumps(dict(samples=len(rows),simulation_time_s=str(rows[-1][0]),last_step_s=str(step[-1]),linear_solves=len(solves))))
