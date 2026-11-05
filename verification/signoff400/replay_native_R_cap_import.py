"""Replay the actual native decimal-to-float conversion and ordered additions."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('build/signoff400').resolve();previous=base/'startup_timing_R_cap_redistribution_002/assessment.json'
    groups=previous.parent/'groups.jsonl';ext=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/Prototype400_FilledCapacitanceView.ext')
    source=Path('tools/sheet_charge/replay_native_R_cap_import.cpp').resolve()
    native=Path('/tmp/openpll-magic-origin-source-zi_pqp3t/source')
    port=native/'utils/port.c';types=native/'resis/resis.h';read=native/'resis/ResReadExt.c'
    headers=[Path('tools/charge_compiler/json.hpp').resolve(),Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()]
    paths=[previous,groups,ext,source,port,types,read,*headers,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths};p=json.loads(previous.read_text())
        if p['artifacts'][str(groups)]!=pins[str(groups)] or p['input_sha256'][str(ext)]!=pins[str(ext)]:raise ValueError('native source/group lineage differs')
        if 'float\t\tcapacitance;' not in types.read_text() or 'node1->capacitance += MagAtof(argv[COUPLEVALUE]);' not in read.read_text():raise ValueError('native float accumulation semantics changed')
        text=port.read_text();start=text.index('float\nMagAtof(');end=text.index('\n}',start)+2
        header=output/'native_MagAtof.hpp';header.write_text(text[start:end]+'\n')
        binary=output/'replay_native_R_cap_import'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3','-Dlinux','-fno-fast-math','-ffp-contract=off','-I',str(output),str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'controls';fixture.mkdir();fg=fixture/'groups.jsonl';fe=fixture/'input.ext'
        fg.write_text(json.dumps(dict(original_conductor='signal',exported_R_node_C_sum_raw=16777216,incident_coupling_C_raw=16777218))+'\n')
        for name,values,expected in (('native_order',[16777216,1,1],16777216),('reordered',[1,1,16777216],16777218)):
            fe.write_text(''.join(f'cap "signal" "unselected" {n}\n' for n in values));cfg=fixture/f'{name}.json';report=fixture/f'{name}.report.json';rows=fixture/f'{name}.groups.jsonl'
            save(cfg,dict(groups=str(fg),ext=str(fe),deadline_uptime=deadline,report=str(report),group_output=str(rows)))
            execute([binary,cfg],fixture/f'{name}.log',deadline,4)
            if json.loads(rows.read_text())['native_float32_import_raw']!=expected:raise ValueError('source-order sensitivity control')
        cfg=output/'config.json';report=output/'report.json';rows=output/'groups.jsonl'
        save(cfg,dict(groups=str(groups),ext=str(ext),deadline_uptime=deadline,report=str(report),group_output=str(rows)))
        execute([binary,cfg],output/'native.log',deadline,4)
        result=json.loads(report.read_text())
        if result['selected_groups']!=p['results']['selected_groups'] or result['original_coupling_records_scanned']!=p['results']['original_coupling_records_scanned']:raise ValueError('complete replay coverage')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('replay input changed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,header,report,rows)},
             every_selected_group_native_float32_C_import_replayed_in_source_order=True,
             actual_native_MagAtof_function_compiled=True,order_sensitive_float32_controls_pass=True,
             results=result,remaining_distribution_errors_diagnostic_not_qualification_bounds=True,
             full_SPICE_matrix_equivalence_verified=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
