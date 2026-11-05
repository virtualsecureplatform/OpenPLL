"""Bind every interstage buffer and connecting net to the immutable routed database."""
import argparse
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease
from bind_CDC_physical_instances import word,inside
from compare_mapped_routed_CDC import identifier


def run(paths_dir,obligations,route,output,endpoint_binding):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    try:
        receipt=paths_dir/'assessment.json';a=json.loads(receipt.read_text());paths_file=paths_dir/'paths.json'
        o_receipt=obligations/'assessment.json';o=json.loads(o_receipt.read_text());o_file=obligations/'obligations.json'
        r_receipt=route/'assessment.json';r=json.loads(r_receipt.read_text());db=route/'route.odb'
        endpoint_receipt=endpoint_binding/'assessment.json'
        if a['input_sha256'].get(str(endpoint_receipt))!=sha(endpoint_receipt):raise ValueError('endpoint binding not pinned by path trace')
        endpoints=json.loads(endpoint_receipt.read_text())
        if (a.get('all_routed_synchronizer_interstage_paths_traced') is not True
                or a['input_sha256'].get(str(o_receipt))!=sha(o_receipt)
                or endpoints['input_sha256'].get(str(r_receipt))!=sha(r_receipt)):
            raise ValueError('matching complete path and physical endpoint lineage required')
        helper=Path(__file__).with_name('bind_CDC_physical_instances.py');image=ROOT/'build/apptainer/openpll-release-modern.sif'
        openroad=next(p for p in r['input_sha256'] if p.endswith('/bin/openroad'))
        pins_paths=[receipt,paths_file,o_receipt,o_file,r_receipt,db,endpoint_receipt,helper,image,Path(__file__).resolve()]
        status('waiting_for_complete_interstage_physical_binding_lease')
        with lease(1,4,deadline):
            pins={str(p):sha(p) for p in pins_paths}
            expected={str(paths_file):a['artifacts'][str(paths_file)],str(o_file):o['artifacts'][str(o_file)],
                      str(db):r['artifacts'][str(db)],str(endpoint_receipt):a['input_sha256'][str(endpoint_receipt)]}
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('interstage physical source changed')
            declarations={c['id']:c for c in json.loads(o_file.read_text())['synchronizers']};chains=[]
            for path in json.loads(paths_file.read_text())['paths']:
                first,last=declarations[path['id']]['stages']
                cells=[dict(first,input_pin=None,output_pin='Q'),*path['intermediate_cells'],dict(last,input_pin='D',output_pin=None)]
                chains.append(dict(id=path['id'],role=path['role'],cells=cells))
            tsv=output/'physical.tsv';script=output/'query.tcl'
            text=f'read_db {word(str(db))}\nset block [ord::get_db_block]\nset out [open {word(str(tsv))} w]\n'
            text+='puts $out [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]\n'
            text+='''proc lookup {block candidates} {
 set found {}
 foreach name $candidates {
  set inst [$block findInst $name]
  if {$inst ne {NULL} && $inst ni $found} {lappend found $inst}
 }
 if {[llength $found]!=1} {error {missing or ambiguous interstage physical instance}}
 return [lindex $found 0]
}
'''
            for chain in chains:
                name=word(chain['id'])
                for index,cell in enumerate(chain['cells']):
                    raw=cell['routed_cell'];canonical=identifier(raw);candidates=list(dict.fromkeys([raw,canonical,'\\'+canonical]))
                    text+=f'set inst [lookup $block [list {" ".join(map(word,candidates))}]]\nlassign [$inst getLocation] x y\n'
                    text+=f'puts $out [join [list CELL {name} {index} [$inst getName] [[$inst getMaster] getName] $x $y [$inst getOrient]] "\\t"]\n'
                    terminals=list(dict.fromkeys(p for p in (cell['input_pin'],cell['output_pin']) if p))
                    text+=f'foreach pin {{{" ".join(terminals)}}} {{\n set term [$inst findITerm $pin]\n if {{$term eq {{NULL}} || [$term getNet] eq {{NULL}}}} {{error {{missing interstage physical terminal}}}}\n set net [$term getNet]\n'
                    text+=f' puts $out [join [list PIN {name} {index} $pin [$net getName] [$term getIoType] [expr {{[$net getWire] ne {{NULL}}}}]] "\\t"]\n'
                    if cell['output_pin']:
                        text+=f' if {{$pin eq {word(cell["output_pin"])}}} {{\n foreach fan [$net getITerms] {{puts $out [join [list FANOUT {name} {index} [[$fan getInst] getName] [[$fan getMTerm] getName] [$fan getIoType]] "\\t"]}}\n if {{[llength [$net getBTerms]]!=0}} {{error {{interstage net has external port loading}}}}\n }}\n'
                    text+='}\n'
            text+='close $out\n';script.write_text(text)
            cfg,native=output/'query.json',output/'native_receipt.json';save(cfg,dict(openroad=openroad,openroad_sha256=r['input_sha256'][openroad],
                 script=str(script),native_receipt=str(native),deadline_uptime=deadline))
            status('querying_all_interstage_cells_pins_and_fanout')
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',
                Path(__file__).resolve(),'--inside',cfg],output/'query.log',deadline,4)
            observed={};units=None
            for line in tsv.read_text().splitlines():
                f=line.split('\t')
                if f[0]=='UNITS':
                    if units is not None or len(f)!=2 or int(f[1])<=0:raise ValueError('unique positive database unit scale required')
                    units=int(f[1]);continue
                key=(f[1],int(f[2]))
                if f[0]=='CELL':
                    if len(f)!=8 or key in observed:raise ValueError('unique physical interstage cell required')
                    observed[key]=dict(instance=f[3],master=f[4],origin_dbu=[int(f[5]),int(f[6])],orientation=f[7],pins={},fanout=[])
                elif f[0]=='PIN':
                    if len(f)!=7 or f[3] in observed[key]['pins']:raise ValueError('unique complete interstage pin record required')
                    observed[key]['pins'][f[3]]=dict(net=f[4],direction=f[5],routed_wire_present=f[6]=='1')
                elif f[0]=='FANOUT':
                    if len(f)!=6:raise ValueError('interstage fanout schema')
                    observed[key]['fanout'].append(dict(instance=f[3],pin=f[4],direction=f[5]))
                else:raise ValueError('unknown interstage physical query record')
            if units is None or len(observed)!=sum(len(c['cells']) for c in chains):raise ValueError('incomplete physical path coverage')
            for chain in chains:
                for index,cell in enumerate(chain['cells']):
                    actual=observed[chain['id'],index]
                    if identifier(actual['instance'])!=identifier(cell['routed_cell']) or actual['master']!=cell['routed_master']:
                        raise ValueError('interstage physical instance/master mismatch')
                    if set(actual['pins'])!={p for p in (cell['input_pin'],cell['output_pin']) if p}:raise ValueError('physical pin coverage mismatch')
                    cell['physical']=actual
                for left,right in zip(chain['cells'],chain['cells'][1:]):
                    a_pin=left['physical']['pins'][left['output_pin']];b_pin=right['physical']['pins'][right['input_pin']]
                    if a_pin['net']!=b_pin['net'] or a_pin['direction']!='OUTPUT' or b_pin['direction']!='INPUT':
                        raise ValueError('interstage physical net continuity/direction failure')
                    drivers=[p for p in left['physical']['fanout'] if p['direction']=='OUTPUT']
                    if drivers!=[dict(instance=left['physical']['instance'],pin=left['output_pin'],direction='OUTPUT')]:
                        raise ValueError('interstage net must have its unique expected driver')
            verify(pins);report=output/'binding.json';save(report,dict(database_units_per_micron=units,chains=chains,
                 endpoint_physical_binding=dict(path=str(endpoint_receipt),sha256=pins[str(endpoint_receipt)]),
                 delay_or_metastability_bound_qualified=False,final_parent_GDS_binding_qualified=False))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (script,cfg,native,tsv,report)},
                 all_interstage_cells_pins_and_nets_physically_bound=True,all_interstage_nets_continuous_with_unique_expected_drivers=True,
                 synchronizers=len(chains),physical_cells=len(observed),intermediate_cells=sum(len(c['cells'])-2 for c in chains),
                 routed_database_modified=False,delay_resolution_or_metastability_bound_qualified=False,
                 final_GDS_connectivity_binding_qualified=False,physical_CDC_qualified=False,release_qualified=False))
            status('complete_interstage_physical_binding_passed',physical_cells=len(observed),synchronizers=len(chains))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path)
    for name in ('paths','obligations','route','output','endpoints'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    elif all((a.paths,a.obligations,a.route,a.output)):run(a.paths.resolve(),a.obligations.resolve(),a.route.resolve(),a.output.resolve(),a.endpoints.resolve())
    else:p.error('paths, obligations, route and output required')
