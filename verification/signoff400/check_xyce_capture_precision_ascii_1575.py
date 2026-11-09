"""One tiny native regression comparing ASCII RAW and explicit standard output."""
import json,os,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute

def run():
    output=ROOT/'build/signoff400/selected_xyce_capture_precision_ascii_1575';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    binary=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'
    raw=output/'probe.raw';standard=output/'probe.prn';deck=output/'probe.spice'
    deck.write_text(f'''Capture precision native regression
Vsource out 0 PWL(0 0 219n 0 220n 0 220.0000001n 1 220.0000002n 0 221n 0)
Rload out 0 1000
.tran 1n 221n 0 1n
.print tran format=raw precision=17 file={raw} V(out)
.print tran format=std precision=17 file={standard} V(out)
.end
''')
    pins={str(p):sha(p) for p in [binary,deck,Path(__file__).resolve()]}
    save(output/'inputs.json',dict(input_sha256=pins,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'status.json',dict(state='waiting_for_resources',release_ready=False))
    try:
        with lease(1,.5,deadline):
            execute([str(binary),'-a','-linsolv','umfpack_reuse',str(deck)],output/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+60),.5)
        times=[];values=[]
        for line in standard.read_text().splitlines():
            fields=line.split()
            if fields and fields[0].isdigit():
                if int(fields[0])!=len(times):raise ValueError('standard sample index mismatch')
                times.append(float(fields[1]));values.append(float(fields[2]))
        if not times or times[0]!=0 or abs(times[-1]-221e-9)>1e-21:raise ValueError('complete standard trace required')
        if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('standard timestamps must be strictly increasing')
        if max(values)<.99:raise ValueError('narrow pulse was not captured')
        with raw.open() as stream:
            for line in stream:
                if line.strip()=='Values:':break
            rt=[]
            for line in stream:
                if not line.strip():continue
                index,t=line.split();rt.append(float(t));next(stream)
        if len(rt)!=len(times):raise ValueError('same native samples required')
        collisions=sum(a==b for a,b in zip(rt,rt[1:]))
        if not collisions:raise ValueError('fixture did not exercise ASCII RAW precision collisions')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [raw,standard,output/'native.log']},
            samples=len(times),RAW_equal_timestamp_pairs=collisions,standard_strict_ordering=True,
            narrow_pulse_preserved=True,standard_precision_17_validated_for_this_fixture=True,
            full_PLL_capture_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_precision_fixture_pass',release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
