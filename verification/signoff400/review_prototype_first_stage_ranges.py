"""Read saved first-stage reports including OpenSTA early/late capacitance ranges."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
from common_v3 import save, sha, verify


def capacitance(section):
    values=re.findall(r'^ Total capacitance: ([0-9.]+)(?:-([0-9.]+))?\s*$',section,re.M)
    if len(values)!=1:
        raise ValueError('unique scalar or ranged capacitance required')
    low,high=values[0];low=float(low);high=float(high) if high else low
    if not 0 <= low <= high or not math.isfinite(high):
        raise ValueError('ordered finite capacitance range required')
    return low*1000,high*1000


def run(source,phase,obligations,output):
    pr=phase/'assessment.json';orr=obligations/'assessment.json'
    p,o=[json.loads(f.read_text()) for f in (pr,orr)]
    for a in (p,o):verify(a['input_sha256']);verify(a['artifacts'])
    original=phase/'screen.tcl';query=source/'query.tcl';table=source/'slews.tsv';log=source/'query.log'
    prefix=original.read_text().split('report_parasitic_annotation',1)[0]
    if not query.read_text().startswith(prefix) or not query.read_text().endswith('close $f\nexit\n'):
        raise ValueError('saved query differs from phase timing inputs')
    chains=json.loads((obligations/'obligations.json').read_text())['synchronizers']
    if len(chains)!=13 or any(c['stages'][0]['routed_master']!='sky130_fd_sc_hs__dfrtp_1' for c in chains):
        raise ValueError('thirteen characterized first-stage masters required')
    rows=list(csv.DictReader(table.open(),delimiter='\t'))
    expected={(c['id'],pin) for c in chains for pin in ('D','CLK','Q','RESET_B')}
    if len(rows)!=52 or {(r['id'],r['pin']) for r in rows}!=expected:
        raise ValueError('all first-stage functional pins must appear exactly once')
    for row in rows:
        for key in ('rise_min_s','rise_max_s','fall_min_s','fall_max_s'):
            row[key]=float(row[key])
            if not math.isfinite(row[key]) or row[key]<0:raise ValueError('invalid pin slew')
    text=log.read_text();script=query.read_text();nets=[]
    if re.search(r'^Error:|\[ERROR ',text,re.M):raise ValueError('native query error')
    for i,c in enumerate(chains):
        name=c['stages'][0]['routed_cell'].lstrip('\\')
        for pin in ('D','CLK','Q','RESET_B'):
            if script.count('set p [sta::get_port_pin_error pin {'+name+'/'+pin+'}]')!=1:
                raise ValueError('query is not bound to each actual first-stage pin')
        start,end=f'FIRST_STAGE_NET_{i}_BEGIN',f'FIRST_STAGE_NET_{i}_END'
        if text.count(start)!=1 or text.count(end)!=1:raise ValueError('incomplete native Q-load report')
        section=text.split(start,1)[1].split(end,1)[0]
        if name+'/Q output ' not in section:raise ValueError('load report driver differs')
        low,high=capacitance(section)
        nets.append(dict(id=c['id'],total_Q_capacitance_min_fF=low,total_Q_capacitance_fF=high))
    files=[pr,orr,original,query,table,log,obligations/'obligations.json',Path(__file__).resolve(),Path(__file__).with_name('common_v3.py')]
    pins={str(f):sha(f) for f in files};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'envelopes.json';save(detail,dict(pins=rows,Q_nets=nets))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        corner=p['native_model_corner'],first_stage_cells=13,functional_pins=52,
        maximum_Q_load_fF=max(n['total_Q_capacitance_fF'] for n in nets),
        maximum_slew_ps_by_pin={pin:max(max(r['rise_max_s'],r['fall_max_s'])*1e12 for r in rows if r['pin']==pin) for pin in ('D','CLK','Q','RESET_B')},
        early_late_capacitance_range_retained=True,read_only_review_of_saved_native_reports=True,
        original_postprocessing_failure_retained=True,native_run_exit_code_not_inferred=True,
        physical_CDC_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','phase','obligations','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('source','phase','obligations','output')))
