"""Check tapped HS macro against library CDL under the routed supply/body ties."""
import argparse,json,time,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute


def run(macro,output):
    output.mkdir(parents=True,exist_ok=False)
    geometry=macro/'ground_access.json';g=json.loads(geometry.read_text());verify(g['input_sha256']);verify(g['artifacts'])
    gds=macro/'sky130_fd_sc_hs__inv_2.gds'
    cdl=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells/inv/sky130_fd_sc_hs__inv_2.cdl'
    pnl=next((ROOT/'build/signoff400/selected_history_keeper_tapped_pdn_1107/config/runs/history_keeper_macros_001/17-openroad-generatepdn').glob('*.pnl.v'))
    text=pnl.read_text()
    for n in [191,195,192,223]:
        cell=re.search(r'history_enable_'+str(n)+r'\s*\((.*?)\);',text,re.S)
        if cell is None or any(x not in cell[1]for x in ['.VNB(VGND)','.VGND(VGND)','.VPB(VPWR)','.VPWR(VPWR)']):
            raise ValueError('routed macro body/supply bindings differ')
    reference=cdl.read_text().replace('sky130_fd_sc_hs__inv_2','keeper_library_inv')
    for old,new in [('MMIN1 ','XMIN1 '),('MMIP1 ','XMIP1 '),(' nfet_01v8_lvt ',' sky130_fd_pr__nfet_01v8_lvt '),(' pfet_01v8 ',' sky130_fd_pr__pfet_01v8 ')]:
        if reference.count(old)!=1:raise ValueError('unexpected source CDL')
        reference=reference.replace(old,new)
    reference+='\n.subckt keeper_reference VNB VPB A Y\nXinv A VNB VNB VPB VPB Y keeper_library_inv\n.ends keeper_reference\n'
    (output/'reference.spice').write_text(reference)
    tcl=output/'extract.tcl';tcl.write_text(f'gds read {gds}\nload sky130_fd_sc_hs__inv_2\nselect top cell\nextract all\next2spice lvs\next2spice -o {output}/extracted.spice\nquit -noprompt\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
    prefix=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',str(output),'--env',f'PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin,PDK_ROOT={pdk}',str(image)]
    commands=[[*prefix,'magic','-dnull','-noconsole','-rcfile',pdk+'/sky130A/libs.tech/magic/sky130A.magicrc',str(tcl)],
              [*prefix,'netgen','-batch','lvs','extracted.spice sky130_fd_sc_hs__inv_2','reference.spice keeper_reference',pdk+'/sky130A/libs.tech/netgen/sky130A_setup.tcl','lvs.rpt','-json']]
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),geometry,gds,cdl,pnl,tcl,output/'reference.spice',image]}
    save(output/'inputs.json',dict(input_sha256=pins,commands=commands))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+300
    with lease(1,4,deadline):
        for command,log in zip(commands,['extract.log','netgen.log']):execute(command,output/log,deadline,4)
    report=(output/'lvs.rpt').read_text();results=json.loads((output/'lvs.json').read_text())
    top=[x for x in results if x.get('name')==['sky130_fd_sc_hs__inv_2','keeper_reference']]
    if len(top)!=1 or 'Final result: Circuits match uniquely.'not in report:raise ValueError('no unique top-level match')
    if any(top[0].get(key)for key in ['badnets','badelements','properties']):raise ValueError('top-level LVS discrepancies')
    verify(pins)
    artifacts=[output/n for n in ['reference.spice','extract.tcl','extracted.spice','extract.log','netgen.log','lvs.rpt','lvs.json']]
    save(output/'assessment.json',dict(input_sha256=pins,commands=commands,artifacts={str(p):sha(p)for p in artifacts},
        standalone_macro_supply_tied_LVS_pass=True,routed_supply_body_bindings_verified=True,top_result=top[0],
        full_routed_LVS_qualified=False,parasitics_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--macro',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.macro.resolve(),a.output.resolve())
