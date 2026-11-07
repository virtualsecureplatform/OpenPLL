"""Replay extraction/LVS from completed keeper GDS with an explicit HS reference."""
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute


def run(route,output):
    output.mkdir(parents=True,exist_ok=False)
    cfgpath=route/'config/config.json';cfg=json.loads(cfgpath.read_text());flow=route/'config/runs/history_keeper_macros_001'
    state=flow/'56-magic-spiceextraction/state_in.json';s=json.loads(state.read_text())
    cdl=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells/inv/sky130_fd_sc_hs__inv_2.cdl'
    text=cdl.read_text()
    for a,b in [('MMIN1 ','XMIN1 '),('MMIP1 ','XMIP1 '),(' nfet_01v8_lvt ',' sky130_fd_pr__nfet_01v8_lvt '),(' pfet_01v8 ',' sky130_fd_pr__pfet_01v8 ')]:
        if text.count(a)!=1:raise ValueError('unexpected CDL format')
        text=text.replace(a,b)
    model=output/'hs_reference.spice';model.write_text(text)
    cfg.update(MAGIC_EXT_USE_GDS=True,MAGIC_EXT_SHORT_RESISTOR=True,
        MAGIC_EXT_ABSTRACT_CELLS=['^sky130_fd_sc_hd__'],EXTRA_SPICE_MODELS=[str(model)])
    config=output/'config.json';save(config,cfg)
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[Path(__file__).resolve(),cfgpath,state,cdl,model,config,image,Path(s['gds']),Path(s['pnl'])]
    pins={str(p):sha(p)for p in paths}
    runner='/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin/librelane'
    command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env','PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin',str(image),runner,'--manual-pdk','--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--run-tag','gds_lvs','--jobs','2','--condensed','--from','Magic.SpiceExtraction','--to','Netgen.LVS','--with-initial-state',str(state),str(config)]
    save(output/'inputs.json',dict(input_sha256=pins,command=command,original_route_unchanged=True,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        with lease(2,8,deadline):execute(command,output/'replay.log',deadline,8)
        verify(pins);save(output/'status.json',dict(state='GDS_LVS_replay_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='GDS_LVS_replay_stopped',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.route.resolve(),a.output.resolve())
