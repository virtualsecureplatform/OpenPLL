"""Verify that a checkpoint reset-source experiment changes only its certified PWL.

Check identical physical network, imported private voltages, native protocol,
other sources, reset endpoints and threshold timing. Independently recompute
the continuous PWL voltage bound on the union of saved knots.
"""
import argparse,bisect,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from selected_native_clock_shapes import load
from bounded_programming_history_sources import crossings


def run(baseline,candidate,output):
    if output.exists():raise FileExistsError(output)
    a,b=[json.loads((p/'manifest.json').read_text())for p in (baseline,candidate)]
    for x in (a,b):verify(x['input_sha256'])
    for key in ('controls','operating_point','observed_roles','native_checkpoint_time_s','simulation_end_s','initialized_private_nodes','DCOP_skipped'):
        if a[key]!=b[key]:raise ValueError('physical initialization or native protocol differs: '+key)
    paths=[Path(__file__).resolve()]
    for filename in ('devices.spice','initial_conditions.spice'):
        if (baseline/filename).read_bytes()!=(candidate/filename).read_bytes():raise ValueError('physical network or initial voltage vector differs')
    if (baseline/'control.spice').read_text().replace(str(baseline),'<RUN>')!=(candidate/'control.spice').read_text().replace(str(candidate),'<RUN>'):
        raise ValueError('native deck changed beyond input/output locations')
    x,y=[sources(p/'sources.spice')for p in (baseline,candidate)]
    if x.keys()!=y.keys():raise ValueError('boundary source set differs')
    reset=a['observed_roles']['reset_driver_input'];changed=[];curves=None
    for node in x:
        if x[node][0]!=y[node][0]:raise ValueError('voltage source identity differs')
        pair=[re.fullmatch(r'PWL FILE "([^"]+)"',v[1])for v in (x[node],y[node])]
        if not any(pair):
            if x[node]!=y[node]:raise ValueError('quiet boundary or supply source differs')
            continue
        if not all(pair):raise ValueError('source type changed')
        left,right=[Path(p[1])for p in pair];paths += [left,right]
        if sha(left)!=sha(right):
            changed.append(node)
            if node==reset:curves=[load(left),load(right)]
    if changed!=[reset] or curves is None:raise ValueError('only the actual reset history may differ')
    left,right=curves
    if left[0]!=right[0] or left[-1]!=right[-1]:raise ValueError('reset initial or final state differs')
    axes=[[t for t,v in row]for row in curves]
    def interpolate(row,axis,t):
        k=bisect.bisect_left(axis,t)
        if k<len(row) and axis[k]==t:return row[k][1]
        if k==0 or k==len(row):raise ValueError('reset extrapolation forbidden')
        return row[k-1][1]+(row[k][1]-row[k-1][1])*(t-axis[k-1])/(axis[k]-axis[k-1])
    union=sorted(set(axes[0])|set(axes[1]))
    maximum=max(abs(interpolate(left,axes[0],t)-interpolate(right,axes[1],t))for t in union)
    if maximum>1e-3:raise ValueError('additional reset voltage perturbation exceeds 1 mV')
    for level in (.18,.9,1.62):
        first,second=[crossings(row,level)for row in curves]
        if len(first)!=len(second) or any(d!=e or abs(t-u)>1e-18 for (t,d),(u,e)in zip(first,second)):
            raise ValueError('reset threshold timing differs')
    receipt=candidate/'reset_voltage_certificate.json';r=json.loads(receipt.read_text())
    if not r['union_knot_voltage_certificate'] or abs(r['maximum_voltage_difference_V']-maximum)>1e-12:
        raise ValueError('independent union-knot result differs from source certificate')
    paths += [receipt]+[p/n for p in (baseline,candidate)for n in ('manifest.json','control.spice','sources.spice','devices.spice','initial_conditions.spice')]
    paths += [Path(__file__).with_name(n)for n in ('common_v3.py','audit_selected_dco_history_inputs.py','selected_native_clock_shapes.py','bounded_programming_history_sources.py')]
    pins={str(p):sha(p)for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,physical_network_private_voltages_and_solver_identical=True,
        all_other_boundary_sources_identical=True,only_reset_PWL_changed=True,
        baseline_reset_knots=len(left),candidate_reset_knots=len(right),
        independent_maximum_reset_voltage_difference_v=maximum,additional_voltage_bound_v=1e-3,
        total_triangle_bound_to_original_native_reset_v=1.001e-3,
        reset_endpoints_and_10_50_90_percent_crossing_times_preserved=True,
        charge_error_bounded=False,DCO_response_equivalence_qualified=False,release_ready=False))
    print('audited reset-only perturbation',len(left),'to',len(right),'knots; maximum error V',maximum)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ('baseline','candidate','output')))
