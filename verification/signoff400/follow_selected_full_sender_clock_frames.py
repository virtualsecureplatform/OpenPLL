"""Measure clock frames as existing full-corner sender packets complete."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease


def run(packets,tt_frame,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        folder=Path(__file__).resolve().parent;worker=folder/'measure_selected_full_sender_clock_frame.py'
        image=ROOT/'build/apptainer/openpll-release-modern.sif';owner_path=packets/'owner.json'
        owner=json.loads(owner_path.read_text());tt=json.loads(tt_frame.read_text());verify(tt['input_sha256'])
        if tt['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8} or not tt['same_full_native_root_and_receiver_source']:
            raise ValueError('source-bound TT frame required')
        helpers=['common_v3.py','resources.py','selected_matching_corner_sender.py','selected_spice_device_conditions.py','selected_native_clock_shapes.py','assess_selected_detector_phase_probe_v4.py','measure_selected_receiver_clock_frame.py','capture_selected_native_initial_snapshot.py']
        paths=[Path(__file__).resolve(),worker,image,owner_path,tt_frame,*[folder/n for n in helpers]]
        pins={str(p):sha(p) for p in paths};verify(pins)
        save(output/'inputs.json',dict(input_sha256=pins,packet_source=str(packets),packet_source_owner=owner,expected_corners=['ff','ss','sf','fs'],native_simulations_launched=0,automatic_identical_retry=False,release_ready=False))
        records=[dict(corner='tt',assessment=str(tt_frame),sha256=sha(tt_frame))]
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12*86400
        for corner in ['ff','ss','sf','fs']:
            while True:
                completed=packets/'completed_packets.json'
                available=json.loads(completed.read_text()) if completed.exists() else []
                matches=[p for p in available if p['corner']==corner]
                if len(matches)>1:raise ValueError('duplicate corner sender packet')
                if matches:break
                state=json.loads((packets/'status.json').read_text()).get('state')
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:
                    raise RuntimeError('original packet observer stopped before '+corner)
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('original native jobs unchanged')
                save(output/'status.json',dict(state='waiting_for_matching_corner_sender_packet',corner=corner,release_ready=False));time.sleep(10)
            record=matches[0];verify(record['artifacts']);verify(pins)
            if record['operating_point']['corner']!=corner:raise ValueError('packet operating point mismatch')
            native=Path(record['source_native']);packet=packets/corner;target=output/corner
            command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image),'python3',str(worker),
                '--native',str(native),'--snapshot',str(packet/'snapshot'),'--waveforms',str(packet/'waveforms'),
                '--reference',str(native.parent/'waveform_assessment'),'--corner',corner,'--output',str(target)]
            save(output/'status.json',dict(state='measuring_matching_corner_receiver_frame',corner=corner,release_ready=False))
            with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600),(output/(corner+'.log')).open('x') as log:
                subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            verify(pins);receipt=target/'assessment.json';a=json.loads(receipt.read_text())
            if a['operating_point']['corner']!=corner or not a['same_full_native_root_and_receiver_source']:
                raise ValueError('actual same-corner source frame required')
            records.append(dict(corner=corner,assessment=str(receipt),sha256=sha(receipt),transport_ps=a['transport_ps']))
            save(output/'completed_frames.json',records)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,frames=records,native_simulations_launched=0,all_five_first_stage_frames_measured=True,second_receiver_clock_measured=False,clock_timing_qualified=False,complete_controller_timing_qualified=False,native_interface_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='five_matching_sender_clock_frames_measured',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_native_jobs_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['packets','tt-frame','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.packets.resolve(),a.tt_frame.resolve(),a.output.resolve())
