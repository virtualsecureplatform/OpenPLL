"""Replay an unqualified fitted detector in Icarus against its native fitting observations."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute

BENCH='''`timescale 1ns/1ps
module bench;
reg refclk=0,feedback=0,reset_n=0;
wire [1:0] bbpd;
integer phase_ps;
Prototype400DetectorModel dut(refclk,feedback,reset_n,bbpd);
initial begin #1.1;reset_n=1;end
initial begin #10.1;refclk=1;forever #20 refclk=~refclk;end
initial begin
 if(!$value$plusargs("phase_ps=%d",phase_ps)) $fatal(1,"missing phase");
 #(10.1+phase_ps/1000.0);feedback=1;forever #20 feedback=~feedback;
end
always @(posedge bbpd[0]) $display("EDGE DN rise %.9f",$realtime);
always @(negedge bbpd[0]) $display("EDGE DN fall %.9f",$realtime);
always @(posedge bbpd[1]) $display("EDGE UP rise %.9f",$realtime);
always @(negedge bbpd[1]) $display("EDGE UP fall %.9f",$realtime);
initial begin #90;$display("DETECTOR_REPLAY_END");$finish;end
endmodule
'''


def run(models,wide,bias,output):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    pins={};artifacts={}
    for folder in (models,wide,bias):
        rp=folder/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts']);pins[str(rp)]=sha(rp)
    widefile=wide/'observations.json';biasfile=bias/'corners.json';model_index=models/'models.json'
    w=json.loads(widefile.read_text());b=json.loads(biasfile.read_text());index=json.loads(model_index.read_text())
    image=ROOT/'build/apptainer/openpll-release-modern.sif';bench=output/'bench.v';bench.write_text(BENCH)
    pins.update({str(p):sha(p) for p in (widefile,biasfile,model_index,image,bench,Path(__file__).resolve())});records=[]
    for m in index:
        corner=m['corner'];model=Path(m['model']);params=Path(m['parameters']);p=json.loads(params.read_text());pins.update({str(f):sha(f) for f in (model,params)})
        folder=output/corner;folder.mkdir();binary=folder/'model.vvp';log=folder/'compile.log'
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home',image,'/usr/bin/iverilog','-g2012','-s','bench','-o',binary,model,bench],log,deadline,4)
        artifacts.update({str(f):sha(f) for f in (log,binary)})
        points=[dict(phase_ps=row['phase_ps'],outputs=row['outputs']) for row in w if row['corner']==corner]
        point_bias=next(row for row in b if row['corner']==corner)
        points.extend(dict(phase_ps=row['phase_ps'],outputs=row['outputs']) for row in point_bias['observations'] if row['phase_ps'] not in p['unresolved_bias_points_ps'])
        for row in points:
            phase=row['phase_ps'];log=folder/f'phase_{phase}ps.log'
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home',image,'/usr/bin/vvp',binary,f'+phase_ps={phase}'],log,deadline,4)
            text=log.read_text()
            if 'DETECTOR_REPLAY_END' not in text:raise ValueError('incomplete behavioral detector replay')
            edges={(role,direction):[] for role in ('DN','UP') for direction in ('rise','fall')}
            for line in text.splitlines():
                f=line.split()
                if f and f[0]=='EDGE':
                    t=float(f[3])
                    if 5<=t<=85:edges[(f[1],f[2])].append(t)
            errors=[];within=True
            for role in ('DN','UP'):
                for direction,key in (('rise','detector_rising_edges_ns'),('fall','detector_falling_edges_ns')):
                    native=row['outputs'][role][key];fitted=edges[(role,direction)]
                    if len(native)!=len(fitted):raise ValueError(f'behavioral/native detector event counts differ: {corner} {phase} {role} {direction}')
                    bounds=p['native_clock_latency_ns'][role][direction]['observed_interval'];half=(bounds[1]-bounds[0])/2
                    delta=[abs(a-b) for a,b in zip(native,fitted)];errors.extend(x*1000 for x in delta)
                    within &= all(x<=half+.00051 for x in delta)
            records.append(dict(corner=corner,phase_ps=phase,paired_clock_edge_error_max_ps=max(errors,default=0),within_observed_fit_band_and_1ps_quantization=within))
            artifacts[str(log)]=sha(log)
    detail=output/'observations.json';save(detail,records);artifacts[str(detail)]=sha(detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,replayed_fit_points=len(records),
        all_fit_event_counts_match=True,all_fit_edges_within_observed_band=all(r['within_observed_fit_band_and_1ps_quantization'] for r in records),
        independent_native_holdout_validation=False,receiver_path_latency_model_included=False,
        diagnostic=True,synthetic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    print('Replayed native fitting points:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--models',type=Path,required=True);p.add_argument('--wide-review',type=Path,required=True);p.add_argument('--bias-review',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.models.resolve(),a.wide_review.resolve(),a.bias_review.resolve(),a.output.resolve())
