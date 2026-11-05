"""Read routed digital-core instance origins for exact GDS-extraction instance reconciliation."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,sha,save,verify
from compiled_charge import execute
from resources import identity,lease
from bind_CDC_physical_instances import inside,word


def run(route,output):
 output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
 save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4))
 lineage=route/'assessment.json';a=json.loads(lineage.read_text())
 db=lineage.parent/'route.odb'
 tool_receipt=lineage;t=json.loads(tool_receipt.read_text());tool=next(p for p in t['input_sha256'] if p.endswith('/bin/openroad'))
 image=ROOT/'build/apptainer/openpll-release-modern.sif';helper=Path(__file__).with_name('bind_CDC_physical_instances.py')
 paths=[lineage,db,tool_receipt,image,helper,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
 if pins[str(db)]!=a['artifacts'][str(db)]:raise ValueError('routed digital database changed')
 script=output/'query.tcl';table=output/'placements.tsv'
 script.write_text('read_db '+word(str(db))+'\nset block [ord::get_db_block]\nset f [open '+word(str(table))+' w]\nputs $f [join [list UNITS [$block getDbUnitsPerMicron]] "\t"]\nforeach inst [$block getInsts] {\n lassign [$inst getOrigin] x y\n set m [$inst getMaster]\n puts $f [join [list INST [$inst getName] [$m getName] [$inst getOrient] $x $y [$m getWidth] [$m getHeight]] "\t"]\n}\nclose $f\n')
 cfg=output/'query.json';native=output/'native_receipt.json';save(cfg,dict(openroad=tool,openroad_sha256=t['input_sha256'][tool],script=str(script),native_receipt=str(native),deadline_uptime=deadline))
 with lease(1,4,deadline):
  execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside',cfg],output/'query.log',deadline,4)
 verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (script,cfg,native,table)},routed_instance_origins_exported=True,geometry_instance_join_complete=False,validated_for_prototype=False,release_ready=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path);p.add_argument('--output',type=Path);p.add_argument('--route',type=Path)
 a=p.parse_args()
 if a.inside:inside(a.inside)
 elif a.output and a.route:run(a.route.resolve(),a.output.resolve())
 else:p.error('route and output required')
