#!/usr/bin/env python3
"""Construct and check passive end states on observed nominal non-device chains.

Synthetic unit-density charge and normalized frequency controls only. Device,
contact, zero-R, PVT, actual C loading and full discretization remain unqualified.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from resources import lease
from nominal_sheet_resistance import parse
from native_axis_stubs import augment,schur_eliminate,port_admittance
from compiled_sheet_charge_registered import build,invoke,payload,decode
TECH=ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
def run(chains,registration,domain,output):
    chains,registration,domain,out=(Path(p).resolve() for p in (chains,registration,domain,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,**extra))
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=8,memory_limit_GiB=8))
    try:
        with lease(8,8,deadline):
            c=json.loads((chains/'assessment.json').read_text());r=json.loads((registration/'assessment.json').read_text());d=json.loads((domain/'assessment.json').read_text())
            if c['input_sha256'].get(str(registration/'assessment.json'))!=sha(registration/'assessment.json') or r['input_sha256'].get(str(domain/'assessment.json'))!=sha(domain/'assessment.json'):raise ValueError('chain/domain lineage mismatch')
            if d['input_sha256'].get(str(TECH))!=sha(TECH):raise ValueError('nominal technology identity mismatch')
            task=domain/'trace/extract.tcl'
            if d['input_sha256'].get(str(task))!=sha(task) or 'extract style ngspice()' not in task.read_text():raise ValueError('nominal native extraction style not established')
            sheet=parse(TECH.read_text());source=chains/'native/chains.jsonl';pins={str(source):c['artifacts'][str(source)]}
            for p in (TECH,task,chains/'assessment.json',registration/'assessment.json',domain/'assessment.json',Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ('nominal_sheet_resistance.py','native_axis_stubs.py','native_axis_basis.py','compiled_sheet_charge_registered.py','common.py','resources.py')]):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native stub input changed')
            save(out/'nominal_sheet_values.json',dict(unit='milliohms_per_square',values={k:str(v) for k,v in sheet.items()},PVT_scaling_qualified=False));selected=[];prepared=[];expected={};dc_checks=0;dynamic=[];scanned=0
            status('constructing_selected_finite_end_states')
            with source.open() as f:
                for line in f:
                    scanned+=1
                    if scanned>200000:break
                    row=json.loads(line);segments=row['segments'];material=row['raw_material']
                    if row['state']!='uncovered_tile_ends' or material not in sheet or len(segments)>6 or any(float(s[4])<=0 for s in segments):continue
                    knots=[(segments[0][0],segments[0][2])]+[(s[1],s[3]) for s in segments];resistances=[F(float(s[4])) for s in segments];box=row['tile_box_internal'];axis=row['flow_axis'];namespace='_stub:'+row['native_group_id']+':'+str(row['native_working_plane_id'])+':'+row['raw_type_id']+':'+str(axis)+':'+','.join(map(str,box));native=defaultdict(F)
                    for (_,a),(_,b),resistance in zip(knots,knots[1:],resistances):
                        g=1/resistance;native[a,a]+=g;native[b,b]+=g;native[a,b]-=g;native[b,a]-=g
                    native={k:v for k,v in native.items() if v};info=dict(source_chain=row,normalized_frequency_only=True,refinements=[])
                    for refinement in (1,2,4):
                        model=augment(box,axis,knots,resistances,sheet[material],namespace,refinement)
                        if schur_eliminate(model['conductance'],model['latent_nodes'])!=native:raise ValueError('end states change original native DC graph')
                        dc_checks+=1;name=str(len(prepared));t=model['template'];prepared.append(dict(id=name,operator=['A',1,0,1,box,1.],source_basis=payload(t,'',point_nodes=t['point_nodes']),target_basis=dict(constant='REF')));expected[name]=model['unit_area_mass']
                        area=F((box[2]-box[0])*(box[3]-box[1]));total_r=sum((edge[2] for edge in model['edges']),F(0));omega=1/float(area*total_r);y,residual=port_admittance(model,knots[0][1],omega)
                        if y.real<0:raise ValueError('positive sheet chain has negative local driving conductance')
                        dynamic.append(residual);info['refinements'].append(dict(refinement=refinement,latent_nodes=len(model['latent_nodes']),end_stubs=len(model['end_stub_nodes']),normalized_omega=omega,admittance=[y.real,y.imag],original_equation_residual=residual))
                    selected.append(info)
                    if len(selected)>=24:break
            if not selected:raise ValueError('no supported uncovered-chain controls')
            save(out/'selected_chains.json',selected);save(out/'input_manifest.json',dict(input_sha256=pins));binary=build(out/'build',deadline);b=json.loads((out/'build/build.json').read_text());pins.update(b['input_sha256']);pins.update(b['artifacts']);status('checking_compiled_complete_tile_unit_mass',cases=len(prepared))
            matrices,_=invoke(binary,prepared,out/'matrices',threads=8,deadline=deadline)
            for m in matrices:
                if decode(m,exact=True)!=expected[m['id']]:raise ValueError('finite-stub full-tile mass differs from analytic area basis')
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native stub input changed during control')
            result=dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (out/'nominal_sheet_values.json',out/'selected_chains.json',out/'build/build.json',out/'matrices/matrices.jsonl')},observed_uncovered_chains=len(selected),exact_native_DC_schur_checks=dc_checks,exact_compiled_full_tile_unit_mass_checks=len(matrices),maximum_normalized_RC_equation_residual=max(dynamic),scanned_chain_records=scanned,new_finite_resistors_and_latent_states=True,synthetic_unit_density_operators=True,normalized_frequency_only=True,physical_400MHz_response_qualified=False,actual_signed_C_attachment_qualified=False,discretization_error_qualified=False,snapshot_selection_qualified=False,contact_impedance_qualified=False,zero_R_model_qualified=False,resistance_units_and_PVT_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('finite_end_state_controls_complete_pending_actual_RC_qualification');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('chains','registration','domain','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();r=run(a.chains,a.registration,a.domain,a.output);print(json.dumps({k:r[k] for k in ('observed_uncovered_chains','exact_native_DC_schur_checks','exact_compiled_full_tile_unit_mass_checks','maximum_normalized_RC_equation_residual','elapsed_s')}))
