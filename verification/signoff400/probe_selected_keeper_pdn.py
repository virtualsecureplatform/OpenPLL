"""Bounded PDN-only replay from a completed keeper floorplan; no original mutation."""
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute


def run(prior,output):
    output.mkdir(parents=True,exist_ok=False)
    cfgpath=prior/'config/config.json'
    state=prior/'config/runs/history_keeper_macros_001/17-openroad-generatepdn/state_in.json'
    cfg=json.loads(cfgpath.read_text());cfg.update(PDN_VWIDTH=1.6,PDN_VSPACING=1.7,KLAYOUT_CONFLICT_RESOLUTION='OverwriteCell')
    save(output/'config.json',cfg)
    # Explicit restart state is read-only; only the new run directory is written.
    state_data=json.loads(state.read_text());odb=Path(state_data['odb'])
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    files=[Path(__file__).resolve(),cfgpath,state,odb,image,output/'config.json']
    for m in cfg['MACROS'].values():
        for key in ['gds','lef']:files.extend(map(Path,m[key]))
    files.append(Path(cfg['PDN_CFG']))
    pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins,release_ready=False))
    runner='/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin/librelane'
    command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env','PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin',str(image),runner,'--manual-pdk','--pdk-root','/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae','--run-tag','pdn_only','--jobs','4','--condensed','--only','OpenROAD.GeneratePDN','--with-initial-state',str(state),str(output/'config.json')]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    try:
        with lease(4,8,deadline):execute(command,output/'pdn.log',deadline,8)
        verify(pins)
        logs=list((output/'runs/pdn_only').glob('*generatepdn/openroad-generatepdn.log'))
        if len(logs)!=1:raise ValueError('expected one PDN log')
        lines=logs[0].read_text().splitlines()
        save(output/'assessment.json',dict(input_sha256=pins,command=command,
            no_via_warnings=[x for x in lines if 'PDN-0110' in x],
            unconnected_instances=[x for x in lines if 'PSM-0039' in x],
            connectivity_failures=[x for x in lines if 'PSM-0069' in x],
            original_inputs_unchanged=True,physical_qualification=False,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='probe_failed',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prior',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.prior.resolve(),a.output.resolve())
