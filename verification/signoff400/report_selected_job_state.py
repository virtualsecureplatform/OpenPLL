"""Report observed controller/worker state without restarting or mutating jobs."""
import argparse,json
from pathlib import Path
from common_v3 import ROOT
from resources import identity

RUNNING={'real_driver_DCO_native_running','corner_detector_native_running','conditional_detector_native_running','reference_forcing_native_running','running_loaded_startup_260ns','DCO_MPI_native_running'}


def read(path):
    try:return json.loads(path.read_text()),None
    except FileNotFoundError:return None,None
    except (OSError,json.JSONDecodeError) as error:return None,type(error).__name__


def live(handle,probe):
    return bool(handle and 'pid' in handle and 'birth' in handle and probe(handle['pid'])==str(handle['birth']))


def inspect(case,leases,probe=identity):
    native=case/'native' if (case/'native').is_dir() else case
    controller,ce=read(case/'owner.json');worker,we=read(native/'native.process.json');owner,oe=read(native/'owner.json');status,se=read(case/'status.json');ns,ne=read(native/'status.json')
    errors={str(p):e for p,e in [(case/'owner.json',ce),(native/'native.process.json',we),(native/'owner.json',oe),(case/'status.json',se),(native/'status.json',ne)] if e}
    declared=status.get('state') if status else None;native_declared=ns.get('state') if ns else None
    controller_live=live(controller,probe);worker_live=live(worker,probe);owner_live=live(owner,probe)
    admitted=bool(owner and any(v.get('pid')==owner.get('pid') and str(v.get('birth'))==str(owner.get('birth')) and live(v,probe) for v in (leases or {}).values()))
    if worker_live:observed='native_worker_live'
    elif errors:observed='observation_pending'
    elif worker:
        observed='native_worker_exited_controller_live' if controller_live else 'native_worker_exited'
    elif owner_live and native_declared in RUNNING and (native/'manifest.json').exists():
        observed='resource_admission_observation_pending' if leases is None else ('starting_native_worker' if admitted else 'waiting_for_resources')
    elif controller_live:observed='controller_live_preparing_or_waiting'
    elif controller:observed='controller_exited'
    else:observed='no_controller_identity_observed'
    return dict(case=str(case),observed_state=observed,declared_state=declared,native_declared_state=native_declared,controller_live=controller_live,native_owner_live=owner_live,worker_live=worker_live,resource_lease_observed=admitted if leases is not None else None,worker_identity=worker,observation_errors=errors,terminal_success_inferred=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True);a=p.parse_args();leases,error=read(ROOT/'build/signoff400/resources/leases.json')
    print(json.dumps(dict(lease_observation_error=error,records=[inspect(c.resolve(),leases) for c in a.case]),indent=2))
