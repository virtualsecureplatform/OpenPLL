"""Run fresh full flattened Magic DRC on an isolated keeper parent assembly."""
import argparse,json,time,os
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease,identity


def run(assembly,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    receipt=assembly/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    gds=assembly/'assembly.gds'
    if not (a.get('replaced_DCO_definition_only')or (a.get('isolated_keeper_parent')and a.get('only_stale_fill_instances_removed'))):raise ValueError('isolated keeper assembly required')
    report=output/'drc_errors.rpt';script=output/'drc.tcl'
    script.write_text(f'crashbackups stop\ndrc euclidean on\ndrc style drc(full)\ndrc on\nsnap internal\ngds flatten true\ngds read {{{gds}}}\nload IntegerPLL_400MHz_PrototypeTop\nselect top cell\nexpand\ndrc catchup\nset f [open {{{report}}} w]\nset count 0\nforeach {{why boxes}} [drc listall why] {{\n puts $f $why\n foreach box $boxes {{incr count;puts $f $box}}\n}}\nputs $f "MAGIC_DRC_RECTANGLES=$count"\nclose $f\nquit -noprompt\n')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),receipt,gds,script,image]};save(output/'inputs.json',dict(input_sha256=pins,release_ready=False))
    command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env','PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin,PDK_ROOT='+pdk,str(image),'magic','-dnull','-noconsole','-rcfile',pdk+'/sky130A/libs.tech/magic/sky130A.magicrc',str(script)]
    try:
        save(output/'status.json',dict(state='keeper_parent_flat_DRC_running',release_ready=False))
        with lease(1,12,deadline):execute(command,output/'native.log',deadline,12)
        verify(pins);lines=report.read_text().splitlines();counts=[int(x.split('=')[1])for x in lines if x.startswith('MAGIC_DRC_RECTANGLES=')]
        if len(counts)!=1:raise ValueError('missing completed DRC count')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [report,output/'native.log']},Magic_full_flat_DRC_rectangles=counts[0],Magic_full_flat_DRC_pass=counts[0]==0,
            parent_LVS_antenna_density_power_and_model_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_parent_flat_DRC_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--assembly',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.assembly.resolve(),a.output.resolve())
