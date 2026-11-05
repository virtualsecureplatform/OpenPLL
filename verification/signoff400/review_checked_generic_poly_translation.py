"""Review actual device-to-model assignments and all fixed-PVT resistor laws."""
import argparse,json,time,os,re
from decimal import Decimal,localcontext
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease


def review(out):
    base=ROOT/'build/signoff400';producer=base/'startup_timing_checked_poly_translation_001';receipt=producer/'assessment.json';a=json.loads(receipt.read_text());old=base/'startup_timing_current_generic_poly_models_003/assessment.json';old_data=json.loads(old.read_text());binding=old.parent/'terminal_bindings.jsonl';fragment=producer/'current_generic_poly_devices.spice';requirements=ROOT/'verification/signoff400/requirements.json';spec=json.loads(requirements.read_text());paths=[receipt,old,binding,fragment,requirements,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    if pins[str(old)]!=a['input_sha256'][str(old)] or pins[str(binding)]!=old_data['artifacts'][str(binding)] or pins[str(fragment)]!=a['artifacts'][str(fragment)]:raise ValueError('current resistor/translation lineage changed')
    bindings={r['instance']:r for r in map(json.loads,binding.read_text().splitlines())};cards={}
    for line in fragment.read_text().splitlines():
        if not line or line.startswith('*'):continue
        tokens=line.split()
        if len(tokens)!=4 or tokens[0] in cards:raise ValueError('unique exact resistor device cards')
        cards[tokens[0]]=tokens
    if cards.keys()!=bindings.keys() or len(cards)!=24:raise ValueError('complete current device coverage')
    geometries=[('0.48','0.5'),('0.51','0.045')]
    for name,b in bindings.items():
        geometry=(b['native_parameters']['w'],b['native_parameters']['l']);expected=[name,*['_v'+str(t['constrained_voltage_id']) for t in b['terminal_bindings']],'openpll_checked_poly_g'+str(geometries.index(geometry))]
        if cards[name]!=expected:raise ValueError('current geometry or constrained-terminal assignment differs')
    required={(c,t) for c in spec['corners'] for t in spec['temperatures_c']};seen=set();maximum=Decimal(0)
    for row in a['results']:
        point=(row['corner'],row['required_global_temperature_c'])
        if point in seen or point not in required:raise ValueError('exact selected PVT inventory')
        seen.add(point);path=Path(row['model_definitions']);pins[str(path)]=sha(path)
        if pins[str(path)]!=a['artifacts'][str(path)]:raise ValueError('fixed-PVT model changed')
        definitions=re.findall(r'(?m)^\.subckt (\S+) t1 t2\nR0 t1 t2 (\S+)\n\.ends \1$',path.read_text())
        if [n for n,_ in definitions]!=['openpll_checked_poly_g0','openpll_checked_poly_g1']:raise ValueError('only exact supported scalar R definitions')
        with localcontext() as ctx:
            ctx.prec=80;p=row['PDK_parameters'];dt=Decimal(point[1])-30;factor=1+Decimal(str(p['tc1_per_C']))*dt+Decimal(str(p['tc2_per_C2']))*dt*dt
            if p['MC_MM_SWITCH']!=0 or p['tnom_C']!=30:raise ValueError('nominal fixed-temperature law scope')
            for i,((w,l),(_,value)) in enumerate(zip(geometries,definitions,strict=True)):
                exact=Decimal(str(p['rsh_ohms_per_square']))*Decimal(l)/(Decimal(w)-Decimal(10)**6*Decimal(str(p['width_reduction_m'])))*factor;printed=Decimal(value)
                if exact<=0 or printed<=0 or float(value)!=row['evaluated_resistances_ohm'][i]:raise ValueError('positive exact emitted resistor value')
                error=abs(printed-exact)/exact;maximum=max(maximum,error)
                if error>Decimal('1e-14'):raise ValueError('scalar formatting/arithmetic screen exceeded')
        if not row['diagnostic_numeric_screen_pass']:raise ValueError('native/reference response control did not match')
    if seen!=required or not a['all_numeric_screens_pass']:raise ValueError('all 15 fixed-PVT controls required')
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('review source changed')
    save(out/'assessment.json',dict(input_sha256=pins,current_native_devices_independently_bound=24,required_PVT_views=15,scalar_values_independently_recomputed=30,maximum_decimal_vs_emitted_relative_difference=str(maximum),all_actual_geometry_and_terminal_assignments_verified=True,all_native_reference_response_controls_pass=True,original_wrapper_mismatch_preserved=True,fixed_PVT_selection_required=True,noise_equivalence_qualified=False,physical_absolute_intrinsic_capacitance_bound_claimed=False,ordinary_sheet_G_PVT_laws_qualified=False,physical_response_error_enclosure_qualified=False,full_physical_PLL_model_integrated=False,release_qualified=False));save(out/'status.json',dict(state='checked_poly_translation_review_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);producer=ROOT/'build/signoff400/startup_timing_checked_poly_translation_001';owner=json.loads((producer/'owner.json').read_text());deadline=owner['deadline_uptime']+600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_exact_poly_translation_producer',release_qualified=False))
    try:
        while not (producer/'assessment.json').exists():
            if identity(owner['pid'])!=owner['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=owner['deadline_uptime']:raise RuntimeError('poly translation stopped without assessment')
            time.sleep(2)
        with lease(1,1,deadline):review(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
