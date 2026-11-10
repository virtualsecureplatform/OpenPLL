"""Full RC initialization diagnostic with validated call-boundary tracing."""
import argparse,csv,json,math,os,re,time,sys,hashlib
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_runtime import closure
from convert_prototype_ng47_diode_geometry import convert
from prototype_xyce_diode_translation import translate as diode
sys.path.insert(0,str(ROOT/'scripts'))
from sky130_diode_translation_probe import translated_model,MODEL_SHA256


def adapt_diodes(original):
    def caps(text):return [line for line in text.splitlines()if line.split()and line.split()[0].startswith(('R','C'))]
    before=caps(original);text,changes=convert(original);text,count=diode(text)
    fragment=translated_model(27,1,1)
    fragment=re.sub(r'(?m)^\+ CJ=\S+',r'+ CJ={1.3459e-15*sky130_fd_pr__nfet_01v8__ajunction_mult}',fragment)
    fragment=re.sub(r'(?m)^\+ CJSW=\S+',r'+ CJSW={3.6001e-17*sky130_fd_pr__nfet_01v8__pjunction_mult}',fragment)
    adapted=fragment+text
    if caps(adapted)!=before:raise ValueError('literal RC cards changed during diode adaptation')
    return adapted,dict(geometry_template_conversions=changes,diode_templates=count,literal_RC_cards_exactly_preserved=len(before),temperature_C=27)



def bias(pin):
    if pin in ['VPWR','VPB','STARTUP_INCREASING']:return 1.8
    if pin in ['VGND','VNB','REFCLK','RESET_N','PLL_ENABLE']:return 0
    for bus,code in [('STARTUP_COARSE',20),('STARTUP_FINE',112),('KI',1),('KP',2)]:
        m=re.fullmatch(re.escape(bus)+r'\[(\d+)\]',pin)
        if m:return 1.8 if code&(1<<int(m[1]))else 0
    return None


def run(model,output):
    receipt=model/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not (r['exact_source_reconstruction_verified'] and r['signed_nonzero_C_unchanged'] and r['zero_R_preserved'] and r['literal_zero_C_preserved_as_reversible_comments']):raise ValueError('exact reversible zero-C backend view required')
    control=ROOT/'build/signoff400/selected_zero_C_metis_control_1816/assessment.json';cr=json.loads(control.read_text());verify(cr['input_sha256']);verify(cr['artifacts'])
    if not cr['native_nonzero_MNA_entries_exactly_equal'] or not cr['only_zero_C_empty_unknown_removed'] or not cr['analytical_DC_completed']:raise ValueError('native zero-C adapter controls required')
    literal=ROOT/'build/signoff400/selected_reference_alias_native_RC_model_1768/assessment.json';lr=json.loads(literal.read_text());verify(lr['input_sha256']);verify(lr['artifacts'])
    if r['input_sha256'].get(str(literal))!=sha(literal):raise ValueError('audited literal model lineage required')
    audit=ROOT/'build/signoff400/selected_reference_alias_full_RC_audit_1766/assessment.json';ar=json.loads(audit.read_text());verify(ar['input_sha256']);verify(ar['artifacts'])
    if not ar['all_full_RC_checks_pass'] or lr['input_sha256'].get(str(audit))!=sha(audit):raise ValueError('full physical RC audit required')
    corrected=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292'
    build=corrected/'assessment.json';validation=ROOT/'build/signoff400/selected_keeper_corrected_BSIM_AC_1294/assessment.json'
    br,vr=[json.loads(p.read_text())for p in [build,validation]]
    for record in [br,vr]:verify(record['input_sha256']);verify(record['artifacts'])
    binary=corrected/'Xyce'
    if sha(binary)!=br['binary_sha256'] or vr['input_sha256'].get(str(binary))!=sha(binary) or not vr['all_17160_current_geometry_observations_compared']:raise ValueError('validated corrected BSIM backend required')
    trace_build=ROOT/'build/tools/xyce_late_init_trace_1777/assessment.json'
    trace_control=ROOT/'build/signoff400/selected_init_trace_control_1778/assessment.json'
    tr,cr=[json.loads(p.read_text())for p in [trace_build,trace_control]]
    for record in [tr,cr]:verify(record['input_sha256']);verify(record['artifacts'])
    if not tr['trace_only'] or tr['base_binary_sha256']!=sha(binary) or tr['changed_archive_members']!=['N_CIR_Xyce.C.o']:raise ValueError('tracing must preserve all device and solver objects')
    if not (cr['analytical_RC_ladder_pass'] and cr['baseline_and_trace_outputs_identical'] and cr['all_initialization_boundaries_observed']):raise ValueError('checked boundary trace required')
    binary=trace_build.parent/'Xyce'
    if sha(binary)!=tr['binary_sha256']:raise ValueError('trace executable identity changed')
    analysis_build=ROOT/'build/tools/xyce_analysis_trace_1780/assessment.json'
    analysis_control=ROOT/'build/signoff400/selected_init_trace_control_1781/assessment.json'
    ab,ac=[json.loads(p.read_text())for p in [analysis_build,analysis_control]]
    for record in [ab,ac]:verify(record['input_sha256']);verify(record['artifacts'])
    if not ab['trace_only'] or ab['base_binary_sha256']!=sha(binary) or ab['changed_archive_members']!=['N_ANP_AnalysisManager.C.o','N_ANP_DCSweep.C.o']:raise ValueError('exact analysis tracing lineage required')
    if not (ac['analytical_RC_ladder_pass'] and ac['baseline_and_trace_outputs_identical'] and len(ac['analysis_events'])==12):raise ValueError('checked analysis events required')
    binary=analysis_build.parent/'Xyce'
    if sha(binary)!=ab['binary_sha256']:raise ValueError('analysis tracer identity changed')
    step_build=ROOT/'build/tools/xyce_step_trace_1783/assessment.json'
    step_control=ROOT/'build/signoff400/selected_init_trace_control_1784/assessment.json'
    sb,sc=[json.loads(p.read_text())for p in [step_build,step_control]]
    for record in [sb,sc]:verify(record['input_sha256']);verify(record['artifacts'])
    if not sb['trace_only'] or sb['base_binary_sha256']!=sha(binary) or sb['changed_archive_members']!=['N_ANP_DCSweep.C.o','N_NLS_NonLinearSolver.C.o']:raise ValueError('exact step tracing lineage required')
    if not (sc['analytical_RC_ladder_pass'] and sc['baseline_and_trace_outputs_identical'] and sc['step_events']):raise ValueError('checked step trace required')
    binary=step_build.parent/'Xyce'
    if sha(binary)!=sb['binary_sha256']:raise ValueError('step tracer identity changed')
    linear_build=ROOT/'build/tools/xyce_linear_trace_1786/assessment.json'
    linear_control=ROOT/'build/signoff400/selected_init_trace_control_1787/assessment.json'
    lb,lc=[json.loads(p.read_text())for p in [linear_build,linear_control]]
    for record in [lb,lc]:verify(record['input_sha256']);verify(record['artifacts'])
    if not lb['trace_only'] or lb['base_binary_sha256']!=sha(binary) or lb['changed_archive_members']!=['N_LAS_TranSolverFactory.C.o']:raise ValueError('exact linear tracing lineage required')
    if not (lc['analytical_RC_ladder_pass'] and lc['baseline_and_trace_outputs_identical'] and lc['linear_events']):raise ValueError('checked linear phase trace required')
    binary=linear_build.parent/'Xyce'
    if sha(binary)!=lb['binary_sha256']:raise ValueError('linear tracer identity changed')
    ordering_build=ROOT/'build/tools/xyce_metis_ordering_1790/assessment.json'
    ordering_control=ROOT/'build/signoff400/selected_metis_control_assessment_1792/assessment.json'
    ob,oc=[json.loads(p.read_text())for p in [ordering_build,ordering_control]]
    for record in [ob,oc]:verify(record['input_sha256']);verify(record.get('artifacts',{}))
    if not ob['ordering_only'] or ob['base_binary_sha256']!=sha(binary) or ob['changed_archive_members']!=['N_LAS_TranSolverFactory.C.o']:raise ValueError('exact METIS ordering lineage required')
    if not (oc['analytical_divider_within_one_ULP'] and oc['METIS_ordering_observed']):raise ValueError('checked METIS control required')
    binary=ordering_build.parent/'Xyce'
    if sha(binary)!=ob['binary_sha256']:raise ValueError('METIS executable identity changed')
    guess_receipt=ROOT/'build/signoff400/selected_RC_voltage_guess_1823/assessment.json';nodeset_control=ROOT/'build/signoff400/selected_nodeset_release_control_1824/assessment.json'
    gr,nr=[json.loads(p.read_text())for p in [guess_receipt,nodeset_control]]
    for record in [gr,nr]:verify(record['input_sha256']);verify(record['artifacts'])
    if gr['input_sha256'].get(str(receipt))!=sha(receipt) or gr['active_nodes_seeded']!=737762 or gr['wire_edges_used']!=847612:raise ValueError('complete exact-wire projection for this model required')
    if not nr['nodeset_released_before_final_DC'] or not nr['hierarchical_nodeset_accepted']:raise ValueError('native NODESET release control required')
    nodeset=guess_receipt.parent/'nodeset.spice'
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{20});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice';pdk,edges=closure(os.getpid(),library)
    original=model/'model.spice';diode_model=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice')
    if sha(diode_model)!=MODEL_SHA256:raise ValueError('checked diode model hash differs')
    adapted,translation=adapt_diodes(original.read_text());source=output/'backend_model.spice';source.write_text(adapted);save(output/'diode_translation.json',translation);header=[line.split()for line in source.read_text().splitlines()if line.startswith('.subckt ')and not line.split()[1].startswith('__openpll_')]
    if len(header)!=1:raise ValueError('one model root required')
    top,ports=header[0][1],header[0][2:];controls=[]
    for pin in ports:
        value=bias(pin)
        if value is not None:controls.append(('VRESET'if pin=='RESET_N'else'Vbias'+str(len(controls)))+' '+pin+' 0 '+str(value))
    if len(controls)!=35:raise ValueError('expected exact selected external input interface')
    selected=['VPWR','VGND','VNB','VPB','RESET_N','PLLOUT','CONFIG_BUSY','CONFIG_READY','TRACKING','FAILED'];data=output/'dc.csv';deck=output/'smoke.spice'
    deck.write_text('* Diagnostic keeper full physical RC reset operating point\n'+f'.lib "{library}" tt\n.include "{source}"\n'+'\n'.join(controls)+'\nXDUT '+' '.join(ports)+' '+top+'\n.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.include "'+str(nodeset)+'"\n.dc VRESET 0 0 1\n.print dc format=csv precision=17 file='+str(data)+' '+' '.join('v('+p+')'for p in selected)+'\n.end\n')
    folder=Path(__file__).resolve().parent;pins={**pdk,**{str(p):sha(p)for p in [receipt,audit,literal,control,build,validation,trace_build,trace_control,analysis_build,analysis_control,step_build,step_control,linear_build,linear_control,ordering_build,ordering_control,guess_receipt,nodeset_control,nodeset,original,source,diode_model,output/'diode_translation.json',deck,binary,Path(__file__).resolve(),folder/'compiled_charge_v2.py',folder/'capture_selected_native_runtime.py',folder/'convert_prototype_ng47_diode_geometry.py',folder/'prototype_xyce_diode_translation.py',ROOT/'scripts/sky130_diode_translation_probe.py']}};verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,PDK_include_edges=edges,CPU=20,memory_GiB=64,native_cap_s=7200,max_native_cases=1,automatic_identical_retry=False,reset_asserted=True,projected_NODESET_initial_guess=True,nodeset_not_a_physical_clamp=True,distributed_wire_R_included=True,initialization_trace_only=False,METIS_ordering_candidate=True,literal_signed_and_zero_RC_preserved=True,literal_zero_C_in_reversible_comments=True,BSIM_PBSWGD_default_corrected=True,release_ready=False))
    try:
        save(output/'status.json',dict(state='flat_native_reset_DC_running',release_ready=False));start=time.monotonic()
        with lease(1,64,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,64)
        verify(pins);lines=data.read_text().splitlines();reader=csv.reader(lines);headers=next(reader);rows=[]
        for row in reader:
            if row and row[0].startswith('End of'):continue
            if len(row)!=len(headers):raise ValueError('incomplete DC output row')
            values=[float(v)for v in row]
            if not all(math.isfinite(v)for v in values):raise ValueError('nonfinite DC point')
            rows.append(dict(zip(headers,values)))
        if len(rows)!=1:raise ValueError('exactly one completed DC point required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [deck,data,output/'native.log']},elapsed_s=time.monotonic()-start,normal_native_exit=True,distributed_wire_R_included=True,BSIM_PBSWGD_default_corrected=True,finite_reset_DC_point=rows[0],transient_correlation_qualified=False,frequency_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='flat_native_reset_DC_complete',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.model.resolve(),a.output.resolve())
