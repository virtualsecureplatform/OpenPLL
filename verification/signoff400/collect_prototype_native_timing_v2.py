"""Collect retained 27C native cell observations for the current routed master inventory."""
import argparse,json,math,re
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify


def run(route,output):
    receipt=route/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    auxiliaries={'fill','tapvpwrvgnd','decap','conb','diode'}
    logic={m for m in r['cell_inventory'] if m.split('__')[1].rsplit('_',1)[0] not in auxiliaries}
    base=ROOT/'build/timing400/release_001'
    campaigns=[('combinational',base/'compact_nominal_15PVT_completion_001/assessment.json'),('sequential',base/'compact_sequential_15PVT_completion_001/assessment.json'),('combinational',ROOT/'build/signoff400/startup_timing_mux2_4_15PVT_raw_001/assessment.json')]
    paths=[receipt,PROFILE,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};observations=[];metadata_context=[];coverage={c:set() for c in ('tt','ff','ss','sf','fs')}
    for kind,campaign in campaigns:
        c=json.loads(campaign.read_text());pins[str(campaign)]=sha(campaign);selected=set()
        for entry in c.get('reused_completed_points',[])+c['case_results']:
            native=Path(entry['assessment']);plan=Path(entry.get('plan',native.parent.parent/'plan.json'));p=json.loads(plan.read_text());point=p['pvt']
            if point['temperature_c']!=27:continue
            corner=point['corner']
            if corner not in coverage or corner in selected or point['supply_v']!=1.8:raise ValueError('unique five-corner 27C/1.8V observations required')
            selected.add(corner)
            if sha(native)!=entry['assessment_sha256']:raise ValueError('retained native receipt changed')
            n=json.loads(native.read_text())
            if not n['all_native_waveform_events_terminal'] or n['passing']!=len(p['fixtures']) or n['fixtures']!=len(p['fixtures']):raise ValueError('complete passing native fixture batch required')
            if len(n['records'])!=len(p['fixtures']) or [x['case_index'] for x in n['records']]!=list(range(len(p['fixtures']))):raise ValueError('native fixture indexing differs')
            for path,digest in {**n['input_sha256'],**n['artifacts']}.items():
                if path==str(ROOT/'verification/active_release.json'):
                    current=sha(path)
                    metadata_context.append(dict(path=path,historical_sha256=digest,current_sha256=current,
                        role='global release-selection/status metadata; not an isolated-cell native fixture input'))
                    pins[path]=current
                    continue
                if path in pins and pins[path]!=digest:raise ValueError('mixed native input/artifact versions')
                pins[path]=digest
            pins[str(native)]=sha(native);pins[str(plan)]=sha(plan)
            for fixture,record in zip(p['fixtures'],n['records']):
                master=fixture['master']
                if master not in logic:continue
                if record['passed'] is not True:raise ValueError('nonpassing native cell observation')
                coverage[corner].add(master)
                observations.append(dict(corner=corner,temperature_c=27,supply_v=1.8,kind=kind,
                    native_receipt=str(native),fixture=fixture,observed=record,
                    input_slew_20_to_80_ns=fixture['full_ramp_ps']*.6/1000,
                    external_load_pf=fixture['external_load_pf']))
        if selected!=set(coverage):raise ValueError('missing five-corner retained batch')
    verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'observations.json';save(detail,observations)
    context=output/'metadata_context.json';save(context,metadata_context)
    missing={c:sorted(logic-values) for c,values in coverage.items()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail),str(context):sha(context)},
        mutable_global_release_metadata_not_used_to_qualify_cell_observations=True,
        candidate_source_sha256=r['candidate_source_sha256'],routed_logic_masters=len(logic),retained_native_fixtures=len(observations),
        missing_masters_by_corner=missing,all_routed_logic_masters_have_retained_five_corner_observations=not any(missing.values()),
        model_to_final_cell_geometry_correlated=False,load_and_slew_envelope_verified=False,
        native_timing_views_qualified=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--route',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.route.resolve(),a.output.resolve())
