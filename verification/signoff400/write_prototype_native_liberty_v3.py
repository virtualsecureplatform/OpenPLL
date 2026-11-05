"""Write diagnostic early/late native views, including sampled constraints and the inherited PDK output slew limit."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
from common_v3 import ROOT, save, sha, verify
from audit_prototype_final_campaign_coverage_v3 import merge_pins


def vector(values):return ', '.join(f'{x:.12g}' for x in values)


def table(name,template,xs,ys,values):
    if len(values)!=len(xs) or any(len(row)!=len(ys) for row in values):raise ValueError('timing table dimensions differ')
    rows=',\n'.join('      '+json.dumps(vector(row)) for row in values)
    return (f'    {name} ({template}) {{\n      index_1 ("{vector(xs)}");\n'
            f'      index_2 ("{vector(ys)}");\n      values (\n{rows}\n      );\n    }}\n')


def observed_table(surface,view,allowance):
    grid=surface['native_grid']
    if view=='early':
        values=[[v-surface['observed_lower_extension_ns']-allowance for v in row] for row in grid['lower_ns']]
    elif view=='late':
        values=[[v+surface['observed_upper_extension_ns']+allowance for v in row] for row in grid['upper_ns']]
    else:raise ValueError('early or late timing view required')
    if surface['metric']=='slew':values=[[max(0,v) for v in row] for row in values]
    return grid['input_slew_20_to_80_ns'],grid['external_load_pf'],values


def render(corner,view,masters,surfaces,constraints,definitions,senses,diode_cap,allowance,default_max_transition):
    text=f'''/* Diagnostic native {corner} {view}: finite holdout margins; qualification pending.
Input pin capacitances are supplied TT25 data, including the conditional diode screen. */
library (prototype_{corner}_{view}) {{
 delay_model : table_lookup;
 default_max_transition : {default_max_transition:.12g};
 time_unit : "1ns";
 voltage_unit : "1V";
 current_unit : "1mA";
 capacitive_load_unit (1, pf);
 nom_voltage : 1.8;
 nom_temperature : 27;
 nom_process : 1;
 input_threshold_pct_rise : 50;
 input_threshold_pct_fall : 50;
 output_threshold_pct_rise : 50;
 output_threshold_pct_fall : 50;
 slew_lower_threshold_pct_rise : 20;
 slew_lower_threshold_pct_fall : 20;
 slew_upper_threshold_pct_rise : 80;
 slew_upper_threshold_pct_fall : 80;
 default_operating_conditions : {corner}_27;
 operating_conditions ({corner}_27) {{ process : 1; voltage : 1.8; temperature : 27; }}
 lu_table_template (propagation) {{
  variable_1 : input_net_transition; variable_2 : total_output_net_capacitance;
  index_1 ("0.012, 0.12, 1"); index_2 ("0, 0.1, 1");
 }}
 lu_table_template (capture) {{
  variable_1 : constrained_pin_transition; variable_2 : related_pin_transition;
  index_1 ("0.012, 0.12, 1.2"); index_2 ("0.012, 0.12, 0.24");
 }}
'''
    for master in sorted(masters):
        data=definitions[master];capture=constraints.get((corner,master))
        text+=f' cell ({master}) {{\n  area : {data["area"]};\n'
        for name,properties in data.items():
            if name.startswith('pg_pin,'):
                text+=f'  pg_pin ({name[7:]}) {{ pg_type : {properties["pg_type"]}; voltage_name : {json.dumps(properties["voltage_name"])}; }}\n'
            elif name.startswith('ff,'):
                text+='  ff ('+', '.join(name.split(',')[1:])+') {\n'
                for key in ('clocked_on','next_state','clear','preset'):
                    if key in properties:text+=f'   {key} : {json.dumps(properties[key])};\n'
                text+='  }\n'
        if '__diode_' in master:
            text+=f'  dont_use : true;\n  pin (DIODE) {{ direction : input; capacitance : {diode_cap:.12g}; }}\n'
        for name,properties in data.items():
            if not name.startswith('pin,'):continue
            pin=name[4:];direction=properties['direction']
            text+=f'  pin ({pin}) {{\n   direction : {direction};\n'
            if direction=='input':
                cap=max(float(properties[k]) for k in ('capacitance','rise_capacitance','fall_capacitance') if k in properties)
                limit=.24 if capture and pin=='CLK' else 1.
                text+=f'   capacitance : {cap:.12g};\n   max_transition : {limit};\n'
                if properties.get('clock')=='true':text+='   clock : true;\n'
                if capture:
                    x=[v/1000 for v in capture['input_slew_20_to_80_ps']]
                    y=[v/1000 for v in capture['related_clock_slew_20_to_80_ps']]
                    if pin=='CLK':
                        for kind in ('high','low'):
                            text+=f'   min_pulse_width_{kind} : {capture["minimum_tested_clock_pulse_allowance_ps"][kind]/1000:.12g};\n'
                    elif pin=='D':
                        for kind in ('setup','hold'):
                            text+=f'   timing () {{ related_pin : "CLK"; timing_type : {kind}_rising;\n'
                            for transition in ('rise','fall'):
                                values=[[v/1000 for v in row] for row in capture['tables'][kind+'_'+transition+'_ps']]
                                text+=table(transition+'_constraint','capture',x,y,values)
                            text+='   }\n'
                    elif pin in ('RESET_B','SET_B'):
                        for kind in ('recovery','removal'):
                            text+=f'   timing () {{ related_pin : "CLK"; timing_type : {kind}_rising;\n'
                            values=[[v/1000 for v in row] for row in capture['tables'][kind+'_rise_ps']]
                            text+=table('rise_constraint','capture',x,y,values)+'   }\n'
            elif direction=='output':
                text+=f'   function : {json.dumps(properties["function"])};\n'
                arcs=surfaces.get((corner,master,pin),{})
                maxima=[s['native_grid']['external_load_pf'][-1] for arc in arcs.values() for s in arc.values()]
                if maxima:text+=f'   max_capacitance : {min(maxima):.12g};\n'
                for (related,timing),arc in sorted(arcs.items()):
                    if timing=='combinational':sense=senses[master,related]
                    else:sense='positive_unate' if timing=='clear' else 'negative_unate' if timing=='preset' else 'non_unate'
                    text+=f'   timing () {{ related_pin : "{related}"; timing_type : {timing}; timing_sense : {sense};\n'
                    for (transition,metric),s in sorted(arc.items()):
                        xs,ys,values=observed_table(s,view,allowance)
                        field='cell_'+transition if metric=='delay' else transition+'_transition'
                        text+=table(field,'propagation',xs,ys,values)
                    text+='   }\n'
            else:raise ValueError('unsupported functional pin direction')
            text+='  }\n'
        text+=' }\n'
    return text+'}\n'


def run(fit,capture,route,placements,allowance_ps,output):
    receipts=[p/'assessment.json' for p in (fit,capture,route)]
    f,c,r=[json.loads(p.read_text()) for p in receipts]
    if f['masters']!=38 or c['master_corner_constraint_sets']!=25 or not c['all_capture_apertures_bracketed']:
        raise ValueError('complete native propagation and capture data required')
    if allowance_ps<5:raise ValueError('propagation allowance must cover the 2 ps native step')
    source=fit/'surfaces.json';constraints=capture/'constraints.json'
    bank=[Path(f['retained_observation_bank'])]
    if not f.get('final_cell_C_grids_included') or str(bank[0]) not in f['input_sha256']:
        raise ValueError('pointwise final-C grid fit and retained lineage required')
    if len(bank)!=1:raise ValueError('unique retained observation bank required')
    pins={str(p):sha(p) for p in (*receipts,source,constraints,*bank,Path(__file__).resolve(),
          Path(__file__).with_name('audit_prototype_final_campaign_coverage_v3.py'))}
    for record in (f,c,r):merge_pins(pins,record)
    placement_receipt=placements/'assessment.json';physical=json.loads(placement_receipt.read_text())
    if physical['input_sha256'].get(str(receipts[2]))!=sha(receipts[2]):raise ValueError('physical dimensions belong to another route')
    merge_pins(pins,physical);pins[str(placement_receipt)]=sha(placement_receipt)
    lines=(placements/'placements.tsv').read_text().splitlines();units=float(lines[0].split('\t')[1]);areas={}
    for line in lines[1:]:
        fields=line.split('\t')
        if len(fields)!=8 or fields[0]!='INST':raise ValueError('physical instance dimensions malformed')
        master=fields[2];area=int(fields[6])*int(fields[7])/units**2
        if master in areas and areas[master]!=area:raise ValueError('inconsistent master dimensions')
        areas[master]=area
    signs=defaultdict(set)
    for row in json.loads(bank[0].read_text()):
        if row['kind']=='combinational':signs[row['fixture']['master'],row['fixture']['input']].add(row['fixture']['inverted'])
    senses={k:'positive_unate' if v=={False} else 'negative_unate' if v=={True} else 'non_unate' for k,v in signs.items()}
    indexed=defaultdict(lambda:defaultdict(dict))
    rows=json.loads(source.read_text());logic={row['master'] for row in rows}
    for row in rows:
        key=(row['corner'],row['master'],row['output']);arc=(row['related_pin'],row['timing_type']);entry=(row['output_direction'],row['metric'])
        if entry in indexed[key][arc]:raise ValueError('duplicate native surface')
        indexed[key][arc][entry]=row
    captures={(row['corner'],row['master']):row for row in json.loads(constraints.read_text())}
    masters=set(r['cell_inventory'])
    if not logic<=masters:raise ValueError('native logic inventory differs from routed design')
    definitions={};base=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs'
    common=base/'timing/sky130_fd_sc_hs__common.lib.json';pins[str(common)]=sha(common)
    supplied_common=json.loads(common.read_text())
    default_max_transition=float(supplied_common['default_max_transition'])
    if default_max_transition!=1.0:raise ValueError('review updated PDK maximum transition before changing native limits')
    if supplied_common['comp_attribute,capacitive_load_unit']!=[1,'pf']:raise ValueError('supplied pin capacitance units changed')
    for master in masters:
        family=master.split('__')[1].rsplit('_',1)[0]
        if family=='diode':definitions[master]={'area':areas[master]};continue
        candidates=[base/'cells'/family/(master+'__tt_025C_1v80'+suffix) for suffix in ('_ccsnoise.lib.json','.lib.json')]
        path=next((p for p in candidates if p.exists()),None)
        if path is None:
            if family not in ('fill','tapvpwrvgnd','decap'):raise ValueError('missing supplied cell interface '+master)
            definitions[master]={'area':areas[master]}
            continue
        definitions[master]=json.loads(path.read_text());pins[str(path)]=sha(path)
    diode=[Path(p) for p in r['input_sha256'] if p.endswith('/antenna_diode_load.lib')]
    if len(diode)!=1:raise ValueError('conditional diode input cap required')
    caps=re.findall(r'(?<!\w)capacitance\s*:\s*([0-9.eE+-]+)\s*;',diode[0].read_text())
    if len(caps)!=1:raise ValueError('one diode capacitance required')
    pins[str(diode[0])]=sha(diode[0]);verify(pins)
    output.mkdir(parents=True,exist_ok=False);artifacts={}
    for corner in ('tt','ff','ss','sf','fs'):
        for view in ('early','late'):
            target=output/(corner+'_'+view+'.lib')
            target.write_text(render(corner,view,masters,indexed,captures,definitions,senses,float(caps[0]),allowance_ps/1000,default_max_transition))
            artifacts[str(target)]=sha(target)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,libraries=10,
         routed_cell_masters=len(masters),native_logic_cell_masters=len(logic),propagation_engineering_allowance_ps=allowance_ps,
         all_native_capture_constraint_sets_included=True,supplied_TT25_pin_capacitances_used=True,
         auxiliary_physical_only_cell_areas_bound_to_routed_database=True,
         native_propagation_and_constraint_tables_emitted=True,
         supplied_PDK_default_max_transition_ns=default_max_transition,
         output_driver_slew_limit_inherited_from_PDK=True,library_parser_validation_complete=False,
         native_PVT_pin_capacitance_and_routed_path_correlation_complete=False,
         physical_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fit','capture','route','placements','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--propagation-allowance-ps',type=float,default=10)
    a=p.parse_args();run(a.fit.resolve(),a.capture.resolve(),a.route.resolve(),a.placements.resolve(),a.propagation_allowance_ps,a.output.resolve())
