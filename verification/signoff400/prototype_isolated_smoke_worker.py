"""Self-contained functional/native replay worker: no repository imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(inputs,work,forbidden):
    inputs=inputs.resolve();work=work.resolve();manifest=inputs/'manifest.json';m=json.loads(manifest.read_text())
    if any(Path(p).exists() for p in forbidden):raise ValueError('host checkout or scratch remains visible')
    def verify():
        for name,expected in m['files'].items():
            p=Path(name)
            if p.is_absolute() or '..' in p.parts or digest(inputs/p)!=expected:raise ValueError('unsafe path or changed replay input '+name)
    verify();os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    def execute(command,name):
        with (work/name).open('x') as stream:subprocess.run(list(map(str,command)),cwd=work,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=43000)
    binary=work/'functional.vvp'
    execute(['/usr/bin/iverilog','-g2012','-s','tb_calibration_reference_pause','-o',binary,*[inputs/p for p in m['rtl']],inputs/'tb/calibration.v'],'functional_compile.log')
    execute(['/usr/bin/vvp',binary],'functional.log')
    log=(work/'functional.log').read_text()
    if log.count('CALIBRATION_PAUSE_OK')!=2 or any(marker not in log for marker in ('CALIBRATION_RESUME_OK','CALIBRATION_RESET_REPROGRAM_OK')):raise ValueError('functional replay incomplete')
    (work/'.spiceinit').write_bytes((inputs/'native/.spiceinit').read_bytes())
    execute([inputs/'tools/ngspice','-b',inputs/'native/refinement.cir'],'native.log')
    wave=work/'waveform.dat'
    if 'KLU' not in (work/'native.log').read_text() or digest(wave)!=m['native_waveform_sha256']:raise ValueError('native replay differs from pinned waveform or KLU is absent')
    verify()
    result=dict(source_manifest_sha256=digest(manifest),host_checkout_and_scratch_hidden=True,functional_replay_pass=True,native_waveform_byte_identical=True,read_only_inputs_unchanged=True,tool_sha256={str(p):digest(Path(p)) for p in ('/usr/bin/iverilog','/usr/bin/vvp')},staging_smoke_only=True,final_macro_replay_qualified=False,release_ready=False)
    (work/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--forbidden',action='append',default=[])
    a=p.parse_args();run(a.inputs,a.work,a.forbidden)
