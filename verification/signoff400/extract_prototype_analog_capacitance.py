"""Stock hierarchical analog capacitance extraction; parent loading and distributed R remain open."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease

MAGIC='/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic'
PDK=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')

def inside(config):
 c=json.loads(config.read_text());out=Path(c['output']);deadline=c['deadline_uptime'];gds=Path(c['gds'])
 rc=PDK/'libs.tech/magic/sky130A.magicrc';tech=PDK/'libs.tech/magic/sky130A.tech'
 paths=[Path(MAGIC),rc,tech,gds,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 for top in c['tops']:
  folder=out/top;folder.mkdir();script=folder/'extract.tcl'
  script.write_text(f'drc off\ncrashbackups disable\nlocking disable\ngds read {{{gds}}}\nload {top} -dereference\ncd {{{folder}}}\nextract do local\nextract do capacitance\nextract do coupling\nextract no resistance\nextract\next2spice lvs\next2spice hierarchy on\next2spice cthresh 0\next2spice short resistor\next2spice -o capacitance.spice {top}.ext\nquit -noprompt\n')
  execute([MAGIC,'-dnull','-noconsole','-rcfile',rc,script],folder/'magic.log',deadline,16)
  target=folder/'capacitance.spice'
  if not target.exists() or '.subckt '+top not in target.read_text():raise ValueError('analog capacitance extraction missing top')
 verify(pins)
 files=[p for p in out.rglob('*') if p.is_file() and p.name not in ('owner.json','status.json','input_manifest.json','config.json')]
 save(out/'native_assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in files},stock_hierarchical_analog_capacitance_extracted=True,parent_loading_complete=False,distributed_R_complete=False,validated_for_prototype=False,release_ready=False))

def run(layout,reference,out):
 out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
 save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
 a=json.loads((layout/'assessment.json').read_text());ref=json.loads((reference/'assessment.json').read_text());gds=layout/'assembly.gds'
 image=ROOT/'build/apptainer/openpll-release-modern.sif';paths=[layout/'assessment.json',reference/'assessment.json',gds,image,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(gds)]!=a['artifacts'][str(gds)] or ref['input_sha256'].get(str(gds))!=pins[str(gds)]:raise ValueError('analog reference/layout mismatch')
 cfg=out/'config.json';save(cfg,dict(gds=str(gds),tops=[r['top'] for r in ref['analog_hierarchies']],output=str(out),deadline_uptime=deadline))
 save(out/'input_manifest.json',dict(input_sha256=pins))
 try:
  save(out/'status.json',dict(state='waiting_for_analog_capacitance_extraction_lease',release_ready=False))
  with lease(1,16,deadline):
   save(out/'status.json',dict(state='stock_analog_capacitance_extraction_running',release_ready=False))
   execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside',cfg],out/'worker.log',deadline,16)
   verify(pins)
  native=out/'native_assessment.json'
  save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(native):sha(native)},stock_hierarchical_analog_capacitance_extracted=True,parent_loading_complete=False,distributed_R_complete=False,device_geometry_review_complete=False,validated_for_prototype=False,release_ready=False))
  save(out/'status.json',dict(state='analog_capacitance_extraction_complete_review_pending',release_ready=False))
 except BaseException as error:
  save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path)
 for name in ('layout','reference','output'):p.add_argument('--'+name,type=Path)
 a=p.parse_args()
 if a.inside:inside(a.inside)
 elif all((a.layout,a.reference,a.output)):run(a.layout.resolve(),a.reference.resolve(),a.output.resolve())
 else:p.error('layout, reference and output required')
