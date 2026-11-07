"""Measure enabled edge inversion and delay without an invented timing limit."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_einvp_window_replay import read


def crossings(rows,index,threshold=.9):
    events=[]
    for left,right in zip(rows,rows[1:]):
        a,b=left[index]-threshold,right[index]-threshold
        if a<0<=b or a>0>=b:
            events.append(dict(time_s=left[0]+(right[0]-left[0])*(-a)/(b-a),direction='rise'if b>a else'fall'))
    return events


def neighborhoods(inputs,outputs,start,end):
    result=[]
    for previous,event,following in zip(inputs,inputs[1:],inputs[2:]):
        lo=(previous['time_s']+event['time_s'])/2;hi=(event['time_s']+following['time_s'])/2
        if lo<start or hi>end:continue
        captured=[x for x in outputs if lo<=x['time_s']<hi];expected='fall'if event['direction']=='rise'else'rise'
        match=len(captured)==1 and captured[0]['direction']==expected
        result.append(dict(input_time_ns=event['time_s']*1e9,input_direction=event['direction'],expected_output_direction=expected,output_edges=captured,exactly_one_inverted_output_edge=match,delay_ps=(captured[0]['time_s']-event['time_s'])*1e12 if match else None))
    return result


def run(loading,inspection,output):
    if output.exists():raise FileExistsError(output)
    receipt=loading/'assessment.json';a,physical=[json.loads(x.read_text())for x in [receipt,inspection]]
    for r in [a,physical]:verify(r['input_sha256']);verify(r.get('artifacts',{}))
    if not a['both_variants_completed']or a['input_sha256'].get(str(inspection))!=sha(inspection):raise ValueError('same inspected complete enabled pulse comparison required')
    records={};files=[receipt,inspection,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('assess_selected_einvp_window_replay.py')]
    for variant in ['original','external_keeper']:
        records[variant]={}
        for label in ['base','refined']:
            path=loading/variant/(label+'.csv');files.append(path);cc,rows=read(path);keys=[c.lower()for c in cc];cells={}
            for cell in physical['cells']:
                ai=keys.index(('V('+cell['local_to_native_nodes']['A'][0]+')').lower());zi=keys.index(('V(Xcut:'+cell['output_node']+')').lower())
                observations=neighborhoods(crossings(rows,ai),crossings(rows,zi),2.6e-9,6.8e-9)
                if not observations:raise ValueError('nonempty complete enabled edge neighborhoods required')
                cells[cell['output_node']]=observations
            records[variant][label]=cells
    differences={}
    for node in records['original']['refined']:
        left=records['original']['refined'][node];right=records['external_keeper']['refined'][node]
        aligned=len(left)==len(right)and all(l['input_direction']==r['input_direction']and abs(l['input_time_ns']-r['input_time_ns'])<1e-9 for l,r in zip(left,right))
        values=[r['delay_ps']-l['delay_ps']for l,r in zip(left,right)]if aligned and all(x['exactly_one_inverted_output_edge']for x in left+right)else[]
        differences[node]=dict(input_events_aligned=aligned,keeper_minus_original_delay_ps=values)
    observed=[x for variant in records.values()for cells in variant.values()for observations in cells.values()for x in observations]
    output.mkdir(parents=True);save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},threshold_V=.9,threshold_scope='half the nominal 1.8 V rail for edge-delay measurement, not a DC logic qualification limit',enabled_window_ns=[2.6,6.8],pairing='one inverted output edge per complete input-edge Voronoi neighborhood; negative measured delay allowed',observations=records,observed_neighborhoods=len(observed),all_observed_neighborhoods_have_one_inverted_output_edge=all(x['exactly_one_inverted_output_edge']for x in observed),delay_differences=differences,synthetic_TE_pulse_only=True,numerical_timing_limit_applied=False,enabled_logic_or_timing_qualified=False,PLL_frequency_shift_qualified=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['loading','inspection','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.loading.resolve(),a.inspection.resolve(),a.output.resolve())
