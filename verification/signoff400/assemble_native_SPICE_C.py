"""Assemble the complete serialized native SPICE C in the ideal conductor basis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def matrix_values(path):
    values={}
    with path.open('rb') as stream:
        if stream.read(8)!=b'SPCRUN01':raise ValueError('control sparse magic')
        count,=struct.unpack('<Q',stream.read(8))
        for _ in range(count):
            row=stream.read(40);key,=struct.unpack_from('<Q',row);sig,exp=struct.unpack_from('<QH',row,8)
            sign=-1 if exp&0x8000 else 1;exponent=(exp&0x7fff)-16383-63
            if exp&0x7fff==0:exponent=1-16383-63
            values[(key>>32,key&0xffffffff)]=Fraction(sign*sig)*Fraction(2)**exponent
        if stream.read(1):raise ValueError('control trailing data')
    return values


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    scratch=Path(tempfile.mkdtemp(prefix='openpll-native-SPICE-C-',dir='/tmp'))
    (output/'native').symlink_to(scratch,target_is_directory=True)
    base=Path('build/signoff400').resolve()
    coverage=base/'startup_timing_SPICE_cap_endpoint_coverage_001/assessment.json'
    fold=base/'startup_timing_ideal_substrate_references_001/assessment.json'
    upgrade=base/'sparse_merger_upgrade_controls_001/assessment.json'
    c,f,u=[json.loads(p.read_text()) for p in (coverage,fold,upgrade)]
    source=Path('tools/sheet_charge/compile_native_SPICE_C.cpp').resolve()
    header=Path('tools/charge_compiler/json.hpp').resolve()
    sparse=Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()
    names=base/'startup_timing_spatial_conductor_maps_001/native/net_names.jsonl'
    nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    deck=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/retained_rc.spice')
    merger=Path(u['merger_binary'])
    paths=[coverage,fold,upgrade,source,header,sparse,names,nodes,deck,merger,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        if not c['all_nonzero_native_SPICE_capacitor_endpoints_registered'] or c['results']['unresolved_endpoint_names']:
            raise ValueError('complete exact endpoint coverage required')
        if not f['complete_map_serialization_independently_checked'] or f['identified_old_conductors']!=[0,1] or f['declared_substrate']!='VGND':
            raise ValueError('controlled ideal substrate fold required')
        if not u['actual_operator_merge_bytes_identical']:raise ValueError('controlled merger required')
        with lease(8,16,deadline):
            status('hashing_native_matrix_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            for p in (names,nodes,deck):
                if pins[str(p)]!=c['input_sha256'][str(p)]:raise ValueError('native coverage source mismatch')
            if pins[str(merger)]!=u['input_sha256'][str(merger)]:raise ValueError('merger changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            binary=output/'compile_native_SPICE_C'
            with (output/'build.log').open('x') as log:
                subprocess.run(['g++','-std=c++20','-O3','-pthread','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            artifacts={str(binary):sha(binary)}
            def merge_runs(current,where):
                current=list(current);level=0
                if not current:raise ValueError('nonempty native C matrix required')
                while len(current)>1:
                    jobs=[];following=[]
                    for start in range(0,len(current),16):
                        cfg=where/f'merge_{level}_{start}.json';result=where/f'merge_{level}_{start}.bin'
                        save(cfg,dict(inputs=list(map(str,current[start:start+16])),output=str(result),deadline_uptime=deadline))
                        jobs.append((cfg,where/f'merge_{level}_{start}.log'));following.append(result)
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        list(pool.map(lambda job:execute([merger,job[0]],job[1],deadline,2),jobs))
                    for result in following:artifacts[str(result)]=sha(result)
                    current=following;level+=1
                return current[0]
            controls=output/'controls';controls.mkdir()
            fn=controls/'names.jsonl';fn.write_text('[0,"reference"]\n[1,"VGND"]\n[2,"signal"]\n[3,"other"]\n')
            fr=controls/'R.jsonl';fr.write_text(json.dumps(dict(original_conductor='signal',printed_name='signal.n0'))+'\n')
            fd=controls/'deck.spice';fd.write_text('C0 signal.n0 VGND 1f\nC1 other signal -2f\nC2 signal VGND 3e-18\nC3 reference VGND 1f\nC4 other VGND -0\n')
            expected={(0,0):Fraction(1003),(0,1):Fraction(-1003),(1,1):Fraction(-997),(1,2):Fraction(2000),(2,2):Fraction(-2000)}
            for threads in (1,4,8):
                where=controls/f'run_{threads}';where.mkdir();cfg=where/'config.json';report=where/'report.json'
                save(cfg,dict(names=str(fn),native_nodes=str(fr),deck=str(fd),threads=threads,max_accumulator_entries=16,output=str(where/'runs'),deadline_uptime=deadline,report=str(report),unknown_output=str(where/'unknown.jsonl')))
                execute([binary,cfg],where/'compile.log',deadline,8)
                final=merge_runs(sorted((where/'runs').glob('*.bin')),where)
                if matrix_values(final)!=expected:raise ValueError('independent signed C, SI conversion, ideal fold matrix controls')
                r=json.loads(report.read_text())
                if r['capacitor_records']!=5 or r['same_original_conductor_capacitors']!=1 or r['ideal_conductor_nodes']!=3:raise ValueError('control coverage/fold')
            fd.write_text('C0 unknown VGND 1f\n')
            where=controls/'negative';where.mkdir();cfg=where/'config.json'
            save(cfg,dict(names=str(fn),native_nodes=str(fr),deck=str(fd),threads=4,max_accumulator_entries=16,output=str(where/'runs'),deadline_uptime=deadline,report=str(where/'report.json'),unknown_output=str(where/'unknown.jsonl')))
            result=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True)
            save(where/'result.json',dict(returncode=result.returncode,stderr=result.stderr))
            if result.returncode==0:raise ValueError('unknown native endpoint accepted')
            save(output/'controls.json',dict(exact_signed_matrix_SI_and_fold_controls_1_4_8_pass=True,unknown_endpoint_rejected=True))
            cfg=output/'config.json';report=output/'compile_report.json';unknown=output/'unknown_endpoints.jsonl'
            save(cfg,dict(names=str(names),native_nodes=str(nodes),deck=str(deck),threads=8,max_accumulator_entries=500000,output=str(scratch/'runs'),deadline_uptime=deadline,report=str(report),unknown_output=str(unknown)))
            status('compiling_every_native_SPICE_capacitor')
            execute([binary,cfg],output/'native.log',deadline,16)
            r=json.loads(report.read_text())
            if r['capacitor_records']!=c['results']['capacitor_records'] or r['ideal_conductor_nodes']!=f['ideal_native_conductor_nets']:raise ValueError('full native matrix coverage')
            runs=sorted((scratch/'runs').glob('*.bin'))
            if len(runs)!=r['sparse_runs']:raise ValueError('native run coverage')
            for p in runs:artifacts[str(p)]=sha(p)
            status('reducing_full_native_SPICE_C_matrix',sparse_runs=len(runs))
            final=merge_runs(runs,scratch)
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,map(Path,pins)))!=list(pins.values()):raise ValueError('source changed during native matrix assembly')
            for p in (final,report,unknown,output/'controls.json'):artifacts[str(p)]=sha(p)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                 full_serialized_native_SPICE_C_matrix_assembled=True,matrix=str(final),results=r,
                 ideal_substrate_fold_applied=True,spatial_voltage_basis_modified=False,
                 raw_matrix_unit_SI_farads='1e-18',signed_native_capacitances_preserved=True,
                 exact_signed_matrix_SI_and_fold_controls_1_4_8_pass=True,
                 full_SPICE_matrix_equivalence_verified=False,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('full_native_SPICE_C_matrix_assembled')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
