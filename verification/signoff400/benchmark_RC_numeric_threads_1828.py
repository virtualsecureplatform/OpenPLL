"""Bounded thread-scaling experiment on the completed full physical RC matrix.

Measures symbolic and numeric factorization only; no transient qualification.
"""
import json, os, time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import lease, identity
from compiled_charge_v2 import execute


def run():
    base = ROOT / 'build/signoff400'
    capture = base / 'selected_zero_C_backend_CSC_capture_1813'
    receipt = capture / 'assessment.json'
    record = json.loads(receipt.read_text())
    verify(record['input_sha256']); verify(record['artifacts'])
    process = json.loads((capture / 'native.process.json').read_text())
    if identity(process['pid']) == process['birth'] or not record['native_diagnostic_completed']:
        raise ValueError('completed matrix required')
    out = base / 'selected_RC_numeric_threads_1828'
    out.mkdir(exist_ok=False)
    original = ROOT / 'tools/xyce_umfpack/symbolic_replay/replay.c'
    source = original.read_text()
    marker = '    '
    old = 'umfpack_di_free_symbolic(&symbolic);free(ap);free(ai);free(ax);free(h);return status==UMFPACK_OK?0:1;'
    if source.count(old) != 1:
        raise ValueError('pinned replay layout changed')
    new = '''void *numeric=NULL;
 if(status!=UMFPACK_OK)return 1;
 clock_gettime(CLOCK_MONOTONIC,&a);
 status=umfpack_di_numeric(ap,ai,ax,symbolic,&numeric,control,info);
 clock_gettime(CLOCK_MONOTONIC,&b);
 printf("{\\"numeric_status\\":%d,\\"numeric_seconds\\":%.9f,\\"simulation_qualified\\":false}\\n",status,(b.tv_sec-a.tv_sec)+(b.tv_nsec-a.tv_nsec)*1e-9);fflush(stdout);
 umfpack_di_free_numeric(&numeric);
 ''' + old
    cfile = out / 'numeric.c'; cfile.write_text(source.replace(old, new))
    binary = out / 'numeric'
    pins = {str(p): sha(p) for p in [receipt, original, cfile, Path(__file__).resolve()]}
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 1800
    save(out/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()), deadline_uptime=deadline))
    save(out/'inputs.json', dict(input_sha256=pins, threads=[1,2,4,8], memory_GiB=32, cap_s=1800,
         matrix_scope='completed full RC first DC Jacobian', simulation_qualified=False,
         automatic_identical_retry=False))
    try:
        with lease(8,32,deadline):
            os.sched_setaffinity(0,set(range(20,28)))
            execute(['/usr/bin/cc','-O2','-I/usr/include/suitesparse',cfile,'-o',binary,'-lumfpack'],out/'build.log',deadline,32)
            results=[]
            for n in [1,2,4,8]:
                os.sched_setaffinity(0,set(range(20,20+n)))
                save(out/'status.json',dict(state='benchmarking_numeric_factorization',threads=n))
                log=out/f'threads_{n}.log'
                execute(['/usr/bin/env',f'OPENBLAS_NUM_THREADS={n}',f'OMP_NUM_THREADS={n}',f'OMP_THREAD_LIMIT={n}',binary,capture/'matrix'],log,deadline,32)
                rows=[json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
                if len(rows)!=2 or rows[0]['status']!=0 or rows[1]['numeric_status']!=0:
                    raise ValueError('factorization benchmark failed')
                results.append(dict(threads=n,**rows[0],**rows[1]))
            verify(pins)
            save(out/'assessment.json',dict(input_sha256=pins, results=results,
                 artifacts={str(p):sha(p) for p in [binary,*out.glob('threads_*.log')]},
                 simulation_qualified=False, release_ready=False))
            save(out/'status.json',dict(state='benchmark_complete'))
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error)))
        raise

if __name__=='__main__': run()
