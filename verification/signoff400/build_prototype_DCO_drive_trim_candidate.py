"""Route an isolated drive-trim experiment; no candidate adoption or qualification."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from common_v3 import ROOT,PROFILE,save,sha,verify
from resources import lease,identity
from compiled_charge import execute


def revise(text):
    header=text[:text.index('    wire tie_hi;')]
    pg='`INTEGERPLL_SKY130_CELL_PG '
    lines=[header, '    wire tie_hi, tie_lo; wire [2:0] ring; wire [46:0] disable_drive;',
           '    wire [509:0] unused_load;',
           '    (* keep, dont_touch *) sky130_fd_sc_hd__conb_1 tie_cell ('+pg+'.HI(tie_hi), .LO(tie_lo));',
           '    (* keep, dont_touch *) sky130_fd_sc_hd__nand2_8 reset_gate ('+pg+'.A(RESET_N), .B(ring[2]), .Y(ring[0]));']
    for i in range(47):
        lines.append(f'    (* keep, dont_touch *) sky130_fd_sc_hd__einvp_1 coarse_inv_{i} ('+pg+f'.A(COARSETHERMAL_CODE[{i}]), .TE(tie_hi), .Z(disable_drive[{i}]));')
    for stage in (1,2):
        for i in range(55):
            enable='tie_lo' if i<8 else f'disable_drive[{i-8}]'
            lines.append(f'    (* keep, dont_touch *) sky130_fd_sc_hd__einvn_1 drive_{stage}_{i} ('+pg+f'.A(ring[{stage-1}]), .TE_B({enable}), .Z(ring[{stage}]));')
    for i in range(510):
        lines.append(f'    (* keep, dont_touch *) sky130_fd_sc_hd__einvp_1 fine_{i} ('+pg+f'.A(ring[{1+i%2}]), .TE(DCO_THERM[{i//2}]), .Z(unused_load[{i}]));')
    lines += ['    sky130_fd_sc_hd__buf_8 out_buf ('+pg+'.A(ring[2]), .X(PLLOUT));', 'endmodule', '`undef INTEGERPLL_SKY130_CELL_PG', '`default_nettype wire']
    return '\n'.join(lines)+'\n'


def run(output):
    evidence=ROOT/'build/signoff400/prototype_v3_DCO_drive_trim_schematic_bands_002/assessment.json'
    preflight=json.loads(evidence.read_text());verify(preflight['input_sha256']);verify(preflight['artifacts'])
    if not preflight.get('all_five_corners_have_observed_schematic_brackets'):raise ValueError('five-corner schematic preflight required')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    base=ROOT/'openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160';source=ROOT/'sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v'
    original=base/'experiment.json';manifest=json.loads(original.read_text())
    if manifest['source_sha256']!=sha(source):raise ValueError('original routed DCO source changed')
    config=output/'config';config.mkdir();variant=config/'dco_drive_trim_fine510.v';variant.write_text(revise(source.read_text()))
    cfg=json.loads((base/'config.json').read_text());cfg['VERILOG_FILES']=[str(variant)]
    cfg['RT_MIN_LAYER']='met2'
    cfg['KLAYOUT_DRC_THREADS']=4
    cfg['DRT_THREADS']=4
    cfg['STA_THREADS']=4
    original_blackbox=ROOT/'sky130/sky130_fd_sc_hd_pll_blackbox.v'
    blackbox=config/'cells.v'
    bb=original_blackbox.read_text()
    if 'module sky130_fd_sc_hd__einvn_1 (' not in bb:
        bb+='\n(* blackbox *) module sky130_fd_sc_hd__einvn_1(output wire Z, input wire A, TE_B); endmodule\n'
    blackbox.write_text(bb)
    for key in ('CELL_VERILOG_MODELS','CELL_BB_VERILOG_MODELS'):cfg[key]=[str(blackbox)]
    for key,name in (('PNR_SDC_FILE','no_clock.sdc'),('SIGNOFF_SDC_FILE','no_clock.sdc'),('IO_PIN_ORDER_CFG','pin_order.cfg')):
        target=config/name
        if not target.exists():shutil.copyfile(base/name,target)
        cfg[key]=str(target)
    cfgpath=config/'config.json';save(cfgpath,cfg)
    image=ROOT/'build/apptainer/openpll-release-modern.sif';runner='/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin/librelane'
    tag='prototype_drive_trim_fine510_001';flow=config/'runs'/tag
    if flow.exists():raise ValueError('fresh isolated flow required')
    paths=[evidence,original_blackbox,PROFILE,source,original,base/'config.json',blackbox,image,variant,cfgpath,config/'no_clock.sdc',config/'pin_order.cfg',Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env','PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin',image,runner,
             '--manual-pdk','--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--run-tag',tag,'--jobs','4','--condensed',cfgpath]
    save(output/'input_manifest.json',dict(input_sha256=pins,command=list(map(str,command)),
        source_change=dict(controlled_stages=2,always_enabled_units_per_stage=8,thermometer_enabled_units_per_stage=47,fine_loads=510,minimum_route_layer='met2'),
        macro_interface_name=cfg['DESIGN_NAME'],selected=False,release_ready=False))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
    save(output/'status.json',dict(state='waiting_for_isolated_DCO_route_resources',release_ready=False))
    try:
        with lease(4,8,deadline):
            save(output/'status.json',dict(state='isolated_DCO_route_running',release_ready=False));execute(command,output/'route.log',deadline,8)
        verify(pins);gds=flow/'final/gds'/(cfg['DESIGN_NAME']+'.gds');lef=flow/'final/lef'/(cfg['DESIGN_NAME']+'.lef')
        if not gds.exists() or not lef.exists():raise ValueError('flow lacks final macro GDS/LEF')
        artifacts={str(p):sha(p) for p in (gds,lef,flow/'final/odb'/(cfg['DESIGN_NAME']+'.odb')) if p.exists()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,isolated_route_completed=True,
            conventional_extraction_and_native_range_complete=False,physical_candidate_selected=False,
            diagnostic=True,validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='isolated_DCO_route_complete_native_qualification_pending',release_ready=False))
    except BaseException as exc:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
