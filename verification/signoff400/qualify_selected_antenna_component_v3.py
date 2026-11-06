"""Qualify the selected prototype antenna component from direct checked evidence.

A component pass is not a pass of the overall physical or release gate.
The profile is deliberately restricted to one selected GDS and pinned PDK.
"""
import argparse,json,os,time
from pathlib import Path
from fractions import Fraction as F
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def run(manifest,tool_profile,build,rule_controls,diode_control,parent,geometry,paint_proof,process_audit,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{20});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='checking_selected_antenna_component',release_ready=False))
    try:
        paths=[manifest,tool_profile,build,rule_controls,diode_control,parent,geometry,paint_proof,process_audit]
        m,p,b,r,d,n,g,c,a=[json.loads(x.read_text()) for x in paths]
        release_profile=ROOT/'verification/signoff400/requirements_v3.json'
        if p['release_profile_sha256']!=sha(release_profile) or m['profile_sha256']!=sha(release_profile):raise ValueError('current prototype profile required')
        pins={str(x):sha(x) for x in paths+[release_profile,Path(__file__).resolve()]}
        def merge(mapping):
            for path,digest in mapping.items():
                if path in pins and pins[path]!=digest:raise ValueError('conflicting evidence identity: '+path)
                pins[path]=digest
        for record in [b,r,d,n,g,c,a]:merge(record['input_sha256']);merge(record['artifacts'])
        candidate=m['candidate']
        merge(m['input_sha256'])
        for key in ['source_sha256','physical_sha256']:merge(candidate[key])
        if candidate['RTL_binding_sha256'] not in m['input_sha256'].values():raise ValueError('frozen RTL binding digest not covered by manifest')
        selected=[(path,digest) for path,digest in candidate['physical_sha256'].items() if path.endswith('/assembly.gds')]
        if len(selected)!=1 or selected[0][1]!=p['selected_GDS_sha256'] or n['input_sha256'].get(selected[0][0])!=selected[0][1]:raise ValueError('exact selected GDS and native parent required')
        for field,digest_field in [('source_patch','source_patch_sha256'),('toolchain','toolchain_sha256')]:
            path=ROOT/p[field]
            if sha(path)!=p[digest_field] or b['input_sha256'].get(str(path))!=p[digest_field]:raise ValueError('registered rebuild recipe differs from controlled build')
            pins[str(path)]=sha(path)
        templates=[]
        for path in r['input_sha256']:
            if path.endswith('/assessment.json'):
                record=json.loads(Path(path).read_text())
                if any(k.endswith('/sky130A.tech') for k in record.get('input_sha256',{})):templates.append(record)
        if len(templates)!=1:raise ValueError('one pinned native fixture technology receipt required')
        merge(templates[0]['input_sha256']);merge(templates[0]['artifacts'])
        for record in [templates[0],n,a]:
            technologies=[digest for path,digest in record['input_sha256'].items() if path.endswith('/sky130A.tech')]
            if technologies!=[p['technology_sha256']]:raise ValueError('unaltered pinned PDK rules required')
        if not b['source_NAR_verified'] or not b['patch_applied_without_fuzz'] or b['release_tool_replaced']:raise ValueError('source-verified isolated rebuild required')
        installed=b['artifacts'];binaries=[path for path in installed if path.endswith('/install/bin/magic')]
        if len(binaries)!=1:raise ValueError('unique registered executable required')
        for record in [r,d,n,a]:
            if any(record['input_sha256'].get(path)!=digest for path,digest in installed.items()):raise ValueError('checks used a different installed tool closure')
        results=rule_controls.parent/'results.json'
        if r['artifacts'].get(str(results))!=sha(results):raise ValueError('rule results not bound by native receipt')
        rows=json.loads(results.read_text());layers=['poly','li1','metal1','metal2','metal3','metal4','metal5','licon','mcon','via1','via2','via3','via4']
        names={'normal_'+name for name in layers}|{('array_' if name in ['licon','mcon','via1','via2','via3','via4'] else 'pad_')+name for name in layers}
        if len(rows)!=26 or {x['case'] for x in rows}!=names:raise ValueError('complete native rule controls required')
        if not all(x['MOS_geometry_and_connectivity_unchanged'] and ((x['feedback_entries']==0) if x['case'].startswith('normal_') else x['feedback_entries']>0) for x in rows):raise ValueError('native rule control failed')
        if not d['isolated_diode_does_not_protect'] or not d['connected_diode_protects_M3_fixture'] or not d['MOS_channel_geometry_preserved']:raise ValueError('actual connected/isolated diode control required')
        if not n['native_flat_layout_antenna_run_completed'] or n['native_antenna_feedback_entries']!=0 or n['residual_hierarchy_uses']!=0 or n['extracted_flat_MOS_primitives']!=61616:raise ValueError('completed zero-feedback selected parent required')
        if g['input_sha256'].get(str(parent))!=sha(parent) or c['input_sha256'].get(str(parent))!=sha(parent):raise ValueError('geometry/contact proof belongs to another parent')
        if not g['all_checked_mask_regions_preserved'] or not g['extracted_MOS_gate_area_matches_source_poly_diff_intersection'] or not g['source_and_flat_channel_areas_match']:raise ValueError('independent selected masks and gate area required')
        if not c['all_six_actual_contact_masks_contained_by_paint']:raise ValueError('actual contact area containment required')
        if a['input_sha256'].get(str(geometry))!=sha(geometry) or a['input_sha256'].get(str(paint_proof))!=sha(paint_proof):raise ValueError('process audit belongs to other geometry')
        if not all(a[k] for k in ['all_seven_selected_process_views_rechecked','current_stage_components_not_joined_by_future_stubs','all_current_layers_have_zero_conservative_feedback','selected_contact_paint_containment_verified']):raise ValueError('independent current-stage accounting incomplete')
        stages_path=process_audit.parent/'stages.json'
        if a['artifacts'].get(str(stages_path))!=sha(stages_path):raise ValueError('process stage records not bound')
        stages=json.loads(stages_path.read_text())
        if len(stages)!=7 or {x['stage'] for x in stages}!=set(range(7)) or any(x['feedback_entries']!=0 or x['MOS_count']!=61616 or F(x['gate_area_um2'])!=F(n['raw_gate_area_um2_at_1_over_200_grid']) or not x['labels_removed'] or not x['future_metal_and_contacts_absent'] for x in stages):raise ValueError('all seven current process layers required')
        checks={key:True for key in p['checks']}
        expected={'source_verified_build','all_26_matched_rule_controls','local_diode_protection_control','independent_selected_mask_and_gate_area','actual_contact_masks_contained_by_paint','seven_current_stage_connectivity_guards','zero_feedback_all_current_process_layers'}
        if set(checks)!=expected:raise ValueError('registered component check set changed')
        with lease(1,2,deadline):verify(pins)
        evidence=output/'evidence.json';save(evidence,dict(receipts={str(x):sha(x) for x in paths},qualified_executable=binaries[0],selected_GDS=selected[0][0],qualification_scope=p['scope']))
        save(output/'qualification.json',dict(input_sha256=pins,artifacts={str(evidence):sha(evidence)},profile_sha256=sha(release_profile),candidate=candidate,status='pass',component='antenna',validated_for_prototype=True,checks=checks,parent_antenna_qualified=True,qualified_tool_profile=sha(tool_profile),arbitrary_layouts_qualified=False,other_physical_components_qualified=False,complete_physical_gate_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_antenna_component_qualified',release_ready=False));print('selected prototype antenna component: pass')
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    names=['manifest','tool-profile','build','rule-controls','diode-control','parent','geometry','paint-proof','process-audit','output']
    for name in names:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,name.replace('-','_')).resolve() for name in names))
