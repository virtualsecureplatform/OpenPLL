"""Isolated mixed-height keeper macro route; selected physical evidence stays frozen."""
import argparse,json,os,shutil,time,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge import execute


def run(output,pdn_only=False):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        base=ROOT/'build/signoff400/prototype_v3_DCO_fine_grain_high_candidate_001/config'
        receipt=ROOT/'verification/prototype400/selected_history_keeper_RTL_candidate.json'
        evidence=json.loads(receipt.read_text());verify(evidence['input_sha256']);verify(evidence['artifacts'])
        source=ROOT/evidence['candidate_source'];verify({str(source):evidence['candidate_source_sha256']})
        hs=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells/inv'
        master='sky130_fd_sc_hs__inv_2';original_lef=hs/(master+'.lef');gds=hs/(master+'.gds')
        config=output/'config';config.mkdir()
        helper=ROOT/'verification/signoff400/build_selected_keeper_ground_access_v3.py'
        image=ROOT/'build/apptainer/openpll-release-modern.sif'
        subprocess.run(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),
            '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',
            str(helper),'--lef',str(original_lef),'--gds',str(gds),'--output',str(config)],check=True,timeout=60)
        lef=config/(master+'.lef');original_gds=gds;gds=config/(master+'.gds')
        cells=config/'cells.v';cells.write_text((base/'cells.v').read_text()+
            '\n(* blackbox *) module sky130_fd_sc_hs__inv_2(input wire A, output wire Y); endmodule\n')
        macro_v=config/'hs_macro.v';macro_v.write_text('(* blackbox *) module sky130_fd_sc_hs__inv_2(input wire A, output wire Y); endmodule\n')
        variant=config/'dco_history_keeper.v';shutil.copyfile(source,variant)
        cfg=json.loads((base/'config.json').read_text());cfg['VERILOG_FILES']=[str(variant)]
        for key in ['CELL_VERILOG_MODELS','CELL_BB_VERILOG_MODELS']:cfg[key]=[str(cells)]
        for key,name in [('PNR_SDC_FILE','no_clock.sdc'),('SIGNOFF_SDC_FILE','no_clock.sdc'),('IO_PIN_ORDER_CFG','pin_order.cfg')]:
            if not(config/name).exists():shutil.copyfile(base/name,config/name)
            cfg[key]=str(config/name)
        loads=[191,195,192,223]
        hs_lib=ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs/lib/sky130_fd_sc_hs__tt_025C_1v80.lib'
        hs_cdl=hs/(master+'.cdl')
        cfg['MACROS']={master:dict(gds=[str(gds)],lef=[str(lef)],vh=[str(macro_v)],lib={'*':[str(hs_lib)]},spice=[str(hs_cdl)],instances={
            'history_enable_'+str(load):dict(location=[(24.72,54.72,84.72,54.72)[i],(24,24,24,54)[i]],orientation='N')for i,load in enumerate(loads)})}
        cfg['FP_MACRO_HORIZONTAL_HALO']=2;cfg['FP_MACRO_VERTICAL_HALO']=2
        cfg['PDN_HORIZONTAL_HALO']=2;cfg['PDN_VERTICAL_HALO']=2
        pdn=ROOT/'verification/signoff400/selected_history_keeper_pdn.tcl'
        cfg['PDN_CFG']=str(pdn)
        cfg['PDN_VWIDTH']=1.6
        cfg['PDN_VSPACING']=1.7
        cfg['KLAYOUT_CONFLICT_RESOLUTION']='OverwriteCell'
        cfg['ENDCAP_CELL']='sky130_fd_sc_hd__tapvpwrvgnd_1'
        cfg['PDN_MACRO_CONNECTIONS']=[f'history_enable_{n} VPWR VGND VPWR VGND'for n in loads]
        cfgpath=config/'config.json';save(cfgpath,cfg)
        image=ROOT/'build/apptainer/openpll-release-modern.sif'
        runner='/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin/librelane'
        tag='history_keeper_macros_001'
        command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env',
            'PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin',
            str(image),runner,'--manual-pdk','--pdk-root',
            '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae',
            '--run-tag',tag,'--jobs','4','--condensed',str(cfgpath)]
        if pdn_only:command[-1:-1]=['--to','OpenROAD.GeneratePDN']
        pins={str(p):sha(p)for p in [helper,original_gds,config/'ground_access.json',Path(__file__).resolve(),receipt,source,original_lef,gds,lef,cells,macro_v,pdn,hs_lib,hs_cdl,variant,cfgpath,image,base/'config.json',base/'cells.v',config/'no_clock.sdc',config/'pin_order.cfg']}
        if not pdn_only:
            probe=ROOT/'build/signoff400/selected_history_keeper_tapped_pdn_1107/assessment.json'
            evidence=json.loads(probe.read_text());verify(evidence['input_sha256'])
            if not evidence['pdn_connectivity_pass']:raise ValueError('tapped PDN preflight failed')
            pins[str(probe)]=sha(probe)
        save(output/'input_manifest.json',dict(input_sha256=pins,command=command,
            HS_cell_geometry_unchanged=False,only_met1_ground_extension_added=True,HS_placement_class_changed_to_BLOCK=True,
            fixed_HS_instances=loads,HD_row_height_um=2.72,HS_height_um=3.33,
            physical_qualification_pending=True,release_ready=False))
        os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
        save(output/'status.json',dict(state='waiting_for_prior_keeper_route',release_ready=False))
        prior=ROOT/'build/signoff400/selected_history_keeper_ground_access_route_1104'
        prior_owner=json.loads((prior/'owner.json').read_text())
        while not pdn_only and identity(prior_owner['pid'])==prior_owner['birth']:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('prior route observation expired; no restart')
            time.sleep(10)
        save(output/'status.json',dict(state='waiting_for_keeper_route_resources',release_ready=False))
        with lease(4,8,deadline):
            save(output/'status.json',dict(state='keeper_macro_route_running',release_ready=False))
            execute(command,output/'route.log',deadline,8)
        verify(pins);flow=config/'runs'/tag;name=cfg['DESIGN_NAME']
        if pdn_only:
            logs=list(flow.glob('*generatepdn/openroad-generatepdn.log'))
            if len(logs)!=1:raise ValueError('missing PDN log')
            lines=logs[0].read_text().splitlines()
            failures=[x for x in lines if any(t in x for t in ['PDN-0110','PSM-0038','PSM-0039','PSM-0069'])]
            save(output/'assessment.json',dict(input_sha256=pins,pdn_connectivity_warnings=failures,
                pdn_connectivity_pass=not failures,physical_signoff_independently_checked=False,release_ready=False))
            save(output/'status.json',dict(state='keeper_PDN_assessed',release_ready=False));return
        files=[flow/'final/gds'/(name+'.gds'),flow/'final/lef'/(name+'.lef'),flow/'final/odb'/(name+'.odb')]
        if not all(p.exists()for p in files):raise ValueError('missing final physical artifacts')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in files},
            isolated_route_completed=True,physical_signoff_independently_checked=False,
            extracted_analog_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_macro_route_complete_qualification_pending',release_ready=False))
    except BaseException as exc:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdn-only',action='store_true');a=p.parse_args();run(a.output.resolve(),a.pdn_only)
