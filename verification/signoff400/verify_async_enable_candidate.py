"""Check isolated asynchronous-enable RTL wiring and phase/restart regressions.

Uses a synthetic oscillator clock. No physical or analog qualification results.
"""
import argparse,json,os,time,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS

SYNC_BLOCK='''    // Qualify enable in the reference domain before it controls startup state.
    // The raw input still withdraws the existing fast/fine tracking resets.
    (* ASYNC_REG="TRUE" *) reg [1:0] enable_ref_pipe;
    always @(posedge REFCLK or negedge ref_reset_n)
        if(!ref_reset_n) enable_ref_pipe<=0;
        else enable_ref_pipe<={enable_ref_pipe[0],PLL_ENABLE};
    wire enable_ref=enable_ref_pipe[1];
'''


def run(candidate,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    catalog=candidate/'sources.json';a=json.loads(catalog.read_text());verify(a['basis_input_sha256']);sources=sorted(candidate.glob('*.v'))
    if len(sources)!=9:raise ValueError('self-contained nine-source candidate required')
    for p in sources:
        if a['source_sha256'].get(str(p.relative_to(ROOT)))!=sha(p):raise ValueError('candidate source identity differs')
        old=ROOT/'rtl/selected400'/p.name
        if p.name!='IntegerPLL_ProgrammedCore.v' and sha(old)!=sha(p):raise ValueError('only parent enable wiring may differ')
    text=(candidate/'IntegerPLL_ProgrammedCore.v').read_text()
    if text.count(SYNC_BLOCK)!=1 or text.count('.PLL_ENABLE(enable_ref),.STARTUP_COARSE(STARTUP_COARSE),')!=1:raise ValueError('unique intended synchronization change required')
    original=text.replace(SYNC_BLOCK,'').replace('.PLL_ENABLE(enable_ref),.STARTUP_COARSE(STARTUP_COARSE),','.PLL_ENABLE(PLL_ENABLE),.STARTUP_COARSE(STARTUP_COARSE),')
    if original!=(ROOT/'rtl/selected400/IntegerPLL_ProgrammedCore.v').read_text():raise ValueError('candidate includes additional RTL changes')
    bench=Path(__file__).with_name('tb_candidate_async_enable_v2.v');prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image];paths=[catalog,*sources,image,bench,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','prove_handoff_v2.py'))];pins=source_pins();pins.update({str(p):sha(p) for p in paths});verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,scope='Proposed isolated RTL ECO only; selected layout and native run inputs remain pinned.',physical_layout_exists=False,diagnostic=True,synthetic=True,release_ready=False))
    records=[]
    with lease(1,2,deadline):
        tools=('/usr/bin/iverilog','/usr/bin/vvp',YOSYS);tool_hashes={p:subprocess.check_output([str(x) for x in (*prefix,'sha256sum',p)],text=True).split()[0] for p in tools}
        binary=output/'bench.vvp';execute([*prefix,'/usr/bin/iverilog','-g2012','-s','bench','-o',binary,*sources,bench],output/'compile.log',deadline,2)
        for phase in (1,9999,19999,20001,29999,39999):
            for mode in (0,1,2):
                log=output/f'phase_{phase}_mode_{mode}.log';execute([*prefix,'/usr/bin/vvp',binary,f'+PHASE_PS={phase}',f'+MODE={mode}'],log,deadline,2)
                marker=f'ASYNC_ENABLE_CANDIDATE_LOGIC_PASS phase_ps={phase} mode={mode}'
                if log.read_text().count(marker)!=1:raise ValueError('complete explicit phase/mode witness required')
                records.append(dict(phase_ps=phase,mode=mode,passed=True));save(output/'status.json',dict(state='checking_async_enable_candidate',completed=len(records),total=18,release_ready=False))
        script=output/'structure.ys';design=output/'design.json';script.write_text('read_verilog -sv '+' '.join(map(str,sources))+f'\nhierarchy -check -top IntegerPLL_ProgrammedCore\nproc\nopt_clean\nwrite_json {design}\n');execute([*prefix,YOSYS,'-s',script],output/'structure.log',deadline,2)
        m=json.loads(design.read_text())['modules']['IntegerPLL_ProgrammedCore'];q=m['netnames']['enable_ref_pipe']['bits'];matches=[c for c in m['cells'].values() if c['connections'].get('Q')==q]
        if len(q)!=2 or len(matches)!=1:raise ValueError('unique two-bit capture register required')
        c=matches[0]
        if c['type']!='$adff' or c['connections']['D']!=[m['ports']['PLL_ENABLE']['bits'][0],q[0]] or c['connections']['CLK']!=m['ports']['REFCLK']['bits'] or c['connections']['ARST']!=m['netnames']['ref_reset_n']['bits']:raise ValueError('actual two-stage reference capture wiring differs')
        if int(c['parameters']['ARST_VALUE'],2)!=0 or int(c['parameters']['ARST_POLARITY'],2)!=0 or int(c['parameters']['CLK_POLARITY'],2)!=1 or m['netnames']['enable_ref_pipe']['attributes'].get('ASYNC_REG')!='TRUE':raise ValueError('reference capture reset/polarity/attribute differs')
        if m['cells']['startup']['connections']['PLL_ENABLE']!=[q[1]]:raise ValueError('startup must consume only second capture stage')
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,container_tool_sha256=tool_hashes,artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file() and p.name not in ('inputs.json','status.json')},records=records,exactly_one_parent_source_changed=True,actual_two_stage_reference_capture_wiring_verified=True,raw_withdrawal_logic_preserved=True,long_and_short_disable_and_stopped_oscillator_restarts_checked=True,reset_during_tracking_checked=True,stable_tracking_observation_ns=200,release_interface_choice_pending=True,candidate_layout_bound=False,physical_CDC_qualified=False,diagnostic=True,synthetic=True,release_ready=False));save(output/'status.json',dict(state='async_enable_candidate_logic_verified',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.image.resolve(),a.output.resolve())
