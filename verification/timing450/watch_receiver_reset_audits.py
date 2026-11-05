#!/usr/bin/env python3
"""Audit each terminal reset/receiver replay; preserve failures and analog jobs."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from characterize_bbpd import sha, verify


def read_ready(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--replays', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    campaign, replays = args.campaign.resolve(), args.replays.resolve()
    manifest = campaign/'input_manifest.json'
    source = json.loads(manifest.read_text())
    helper = Path(__file__).with_name('audit_receiver_reset_replay.py').resolve()
    pins = {str(p.resolve()):sha(p) for p in [manifest,helper,Path(__file__),
            Path(__file__).with_name('characterize_bbpd.py')]}
    folders = sorted(p.parent for p in campaign.glob('*/loaded.cir'))
    assert len(folders) == source['requested_points'] == 180
    args.output.mkdir(parents=True, exist_ok=False)
    records = {}
    while len(records) < 180:
        verify(pins)
        progress = read_ready(replays/'assessment.json')
        for folder in folders:
            if folder.name in records:
                continue
            native_path = folder/'assessment.json'
            native = read_ready(native_path)
            if native is None:
                continue
            verify(native['sha256'])
            replay_path = replays/folder.name/'assessment.json'
            replay = read_ready(replay_path)
            terminal_replay = progress and folder.name in progress['records']
            if native['simulation_completed'] and native['exit_code']==0 and replay is None and not terminal_replay:
                continue
            record = {'native_assessment':str(native_path),'native_sha256':sha(native_path),
                      'native_completed':native['simulation_completed'],'audit_pass':False}
            if replay is not None:
                record.update(replay_assessment=str(replay_path),replay_sha256=sha(replay_path))
                verify(replay['sha256']);verify(replay['artifacts'])
                if replay['pass'] and replay['exit_code']==0:
                    out = args.output/(folder.name+'.json')
                    with (args.output/(folder.name+'.log')).open('w') as log:
                        result = subprocess.run([sys.executable,str(helper),'--native-directory',str(folder),
                            '--replay-directory',str(replay_path.parent),'--output',str(out)],
                            stdout=log,stderr=subprocess.STDOUT)
                    record['audit_exit_code']=result.returncode
                    if out.exists():
                        audit=json.loads(out.read_text())
                        record.update(audit_pass=audit['pass'] and result.returncode==0,
                                      audit=str(out),audit_sha256=sha(out))
            records[folder.name]=record
            verify(pins)
            report={'requested_points':180,'terminal_points':len(records),
                    'audited_passing_points':sum(r['audit_pass'] for r in records.values()),
                    'all_terminal_audits_pass':all(r['audit_pass'] for r in records.values()),
                    'complete':len(records)==180,'input_pins':pins,'records':records,
                    'release_qualified':False,'selected':False,
                    'scope':'Independent complete-waveform and actual signed/stale RTL consumption audits for reset PVT campaign',
                    'limitations':['450MHz/one reset alignment, nominal internal cellRC/fixed routeRC/ideal controls',
                                   'Measured-storage functional replay; no mapped gate timing, statistical MTBF or fullPLL proof']}
            temporary=args.output/'assessment.tmp'
            temporary.write_text(json.dumps(report,indent=2)+'\n')
            temporary.replace(args.output/'assessment.json')
            print(json.dumps({'terminal_points':len(records),'last_point':folder.name,
                              'audit_pass':record['audit_pass']}),flush=True)
        if len(records)<180:
            time.sleep(10)
    verify(pins)


if __name__=='__main__':
    main()
