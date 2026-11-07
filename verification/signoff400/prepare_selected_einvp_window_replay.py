"""Prepare a 200--210 ns conditional replay from every recorded boundary knot."""
import argparse,csv,json,math,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from capture_selected_native_initial_snapshot import fingerprint
from measure_selected_mos_terminal_extents import header

LIB=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')


def run(cut,offset,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{31})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1800):
        receipt=cut/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        raw=Path(a['raw']);before=fingerprint(raw)
        if before!=a['source_file_fingerprint']:raise ValueError('unchanged source RAW required')
        names,points=header(raw);nodes=a['boundary_nodes']+a['internal_nodes'];indices={a['waveform_bindings'][n]['index']:n for n in nodes}
        marker=offset.read_text().strip().split(':',1)
        if len(marker)!=2:raise ValueError('unique byte-offset marker required')
        byte=int(marker[0]);record=marker[1].split()
        if len(record)!=2 or int(record[0])!=26962 or abs(float(record[1])-200e-9)>1e-20:raise ValueError('expected native 200 ns sample marker required')
        samples=[];expected=26962
        with raw.open('rb')as f:
            f.seek(byte)
            while True:
                line=f.readline()
                while line and not line.strip():line=f.readline()
                row=line.split()
                if len(row)!=2 or int(row[0])!=expected:raise ValueError('complete consecutive native samples required')
                seconds=float(row[1]);values={}
                if not math.isfinite(seconds) or (samples and seconds<=samples[-1][0]):raise ValueError('finite increasing times required')
                for index in range(1,len(names)):
                    line=f.readline()
                    if not line:raise ValueError('truncated native sample')
                    if index in indices:
                        value=float(line)
                        if not math.isfinite(value):raise ValueError('finite boundary voltages required')
                        values[indices[index]]=value
                if len(values)!=len(nodes):raise ValueError('complete waveform bindings required')
                samples.append((seconds,values));expected+=1
                if seconds>=210e-9:break
        if samples[-1][0]>210e-9:
            t0,v0=samples[-2];t1,v1=samples[-1];fraction=(210e-9-t0)/(t1-t0)
            samples[-1]=(210e-9,{n:v0[n]+fraction*(v1[n]-v0[n])for n in nodes})
        if fingerprint(raw)!=before:raise ValueError('native RAW changed')
        output.mkdir(parents=True);csvpath=output/'recorded.csv'
        with csvpath.open('w')as f:
            writer=csv.writer(f);writer.writerow(['time_s']+nodes)
            for t,v in samples:writer.writerow([format(t-200e-9,'.17g')]+[format(v[n],'.17g')for n in nodes])
        source=output/'boundaries.spice'
        with source.open('w')as f:
            for i,n in enumerate(a['boundary_nodes']):
                f.write('Vboundary%d %s 0 PWL(\n'%(i,n))
                for t,v in samples:f.write('+ %.17g %.17g\n'%(t-200e-9,v[n]))
                f.write('+ )\n')
        decks=[]
        for label,step in [('base','0.5p'),('refined','0.25p')]:
            deck=output/(label+'.spice');decks.append(deck)
            text='* Conditional retained-boundary replay; no physical qualification.\n.lib "%s" tt\n.include "%s"\n.include "%s"\n'%(LIB,cut/'cut.spice',source)
            text+='Xcut '+' '.join(a['boundary_nodes'])+' selected_einvp_cut\n'
            text+=''.join('.IC V(Xcut:%s)=%.17g\n'%(n,samples[0][1][n])for n in a['internal_nodes'])
            text+='.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.options timeint reltol=1e-5 abstol=1e-9\n'
            text+='.TRAN %s 10n 0 %s UIC\n'%(step,step)
            text+='.PRINT TRAN FORMAT=CSV FILE="%s" PRECISION=17 '%(output/(label+'.csv'))+' '.join('V(Xcut:%s)'%n for n in a['internal_nodes'])+'\n.END\n'
            deck.write_text(text)
        files=[receipt,offset,LIB,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('measure_selected_mos_terminal_extents.py')]
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},artifacts={str(p):sha(p)for p in [csvpath,source]+decks},recorded_window_ns=[200,210],recorded_knots=len(samples),boundary_nodes=len(a['boundary_nodes']),solved_internal_nodes=len(a['internal_nodes']),initial_conditions_from_native_sample=26962,all_recorded_interior_knots_retained=True,final_endpoint_interpolated=True,maximum_steps_ps=[.5,.25],simulations_executed=False,internal_waveforms_reproduced=False,causality_proven=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['cut','offset','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.cut.resolve(),a.offset.resolve(),a.output.resolve())
