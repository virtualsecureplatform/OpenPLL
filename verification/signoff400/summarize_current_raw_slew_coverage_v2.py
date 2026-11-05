"""Join strict raw combinational outcomes to the exact current master inventory."""
import argparse,json,time
from pathlib import Path
from common import save,sha
from resources import lease


def run(out):
    out.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    coverage=base/'startup_timing_characterization_coverage_002/assessment.json';inventory=coverage.parent/'master_coverage.json';audit=base/'startup_timing_raw_strict_slew_audit_001/assessment.json';mux=base/'startup_timing_mux2_4_15PVT_raw_001/assessment.json';spec=Path('verification/signoff400/requirements.json').resolve()
    paths=[coverage,inventory,audit,mux,spec,Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(1,1,deadline):
        pins={str(p):sha(p) for p in paths};c,m,a,x,r=[json.loads(p.read_text()) for p in paths[:5]]
        if pins[str(inventory)]!=c['artifacts'][str(inventory)]:raise ValueError('current inventory changed')
        required={(k,t,1.8) for k in r['corners'] for t in r['temperatures_c']};masters={k:v for k,v in m.items() if v['raw_combinational_15PVT']};plans={};counts={};nonpassing=[];unused_nonpassing=0
        for name in a['input_sha256']:
            if not name.endswith('/plan.json'):continue
            p=Path(name);pins[name]=sha(p)
            if pins[name]!=a['input_sha256'][name]:raise ValueError('audited plan changed')
            plan=json.loads(p.read_text());pvt=plan['pvt'];key=(pvt['corner'],pvt['temperature_c'],pvt['supply_v'])
            if key in plans:raise ValueError('duplicate retained point')
            plans[key]=plan
        def consume(pvt,fixtures,records):
            nonlocal unused_nonpassing
            point=(pvt['corner'],pvt['temperature_c'],pvt['supply_v'])
            if point not in required or len(fixtures)!=len(records):raise ValueError('complete expected point')
            for i,(fixture,record) in enumerate(zip(fixtures,records,strict=True)):
                if record['case_index']!=i:raise ValueError('case correspondence')
                master=fixture['master'];passed=record['passed'] and record['strict_output_slew_passed']
                if master not in masters:
                    unused_nonpassing+=not passed;continue
                key=(master,point);counts[key]=counts.get(key,0)+1
                if not passed:nonpassing.append(dict(PVT=pvt,fixture=fixture,record=record))
        for result in a['results']:
            report=Path(result['report']);pins[str(report)]=sha(report)
            if pins[str(report)]!=result['report_sha256']:raise ValueError('audited report changed')
            raw=json.loads(report.read_text());pvt=result['PVT'];point=(pvt['corner'],pvt['temperature_c'],pvt['supply_v']);consume(pvt,plans[point]['fixtures'],raw['records'])
        for result in x['case_results']:
            receipt=Path(result['assessment']);plan=receipt.parent.parent/'plan.json'
            raw=json.loads(receipt.read_text())
            for p,expected in [(receipt,result['assessment_sha256']),(plan,raw['input_sha256'][str(plan)])]:
                pins[str(p)]=sha(p)
                if pins[str(p)]!=expected:raise ValueError('mux raw evidence changed')
            raw=json.loads(receipt.read_text());consume(raw['pvt'],json.loads(plan.read_text())['fixtures'],raw['records'])
        if set(counts)!={(master,point) for master in masters for point in required}:raise ValueError('every current combinational master must cover every PVT')
        for master in masters:
            if len({counts[(master,p)] for p in required})!=1:raise ValueError('uniform fixture inventory per master across PVT')
        target=out/'current_combinational_raw_slew_coverage.json';save(target,{k:dict(instances=v['instances'],PVT_points=15,fixtures_per_point=counts[(k,next(iter(required)))]) for k,v in masters.items()})
        if any(sha(Path(p))!=h for p,h in pins.items()):raise ValueError('summary source changed')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target)},current_combinational_masters=len(masters),required_PVT_points=15,current_fixture_PVT_observations=sum(counts.values()),current_nonpassing_observations=nonpassing,unused_master_nonpassing_observations_preserved=unused_nonpassing,all_current_combinational_raw_propagation_and_strict_slew_pass=not nonpassing,all_current_master_PVT_pairs_covered=True,raw_grid_scope_only=True,native_simulations_started=0,strict_failures_waived=False,final_extracted_load_domains_qualified=False,interpolation_qualified=False,sequential_constraints_qualified=False,physical_timing_qualified=False,release_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
