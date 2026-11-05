#!/usr/bin/env python3
"""Give tracing a private exclusive file, isolated from native Tcl diagnostics."""
from pathlib import Path
import difflib
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';prior=base/'magic_full_C_trace_patch_002/assessment.json'
    v=verify(prior)
    for p,d in v['diagnostic_source_files'].items():assert sha(p)==d,p
    out=base/'magic_full_C_trace_patch_003';out.mkdir(exist_ok=False)
    source=ROOT/'build/timing400/magic_location_source_001';patch='';diagnostic={}
    for name in ['ExtBasic.c','ExtCouple.c']:
        p=source/'extract'/name;text=p.read_text()
        original=(base/'magic_full_C_trace_patch_001'/('original_'+name)).read_text()
        if name=='ExtBasic.c':
            marker='int OpenPLLTraceEnabled = 0;';assert text.count(marker)==1
            text=text.replace(marker,marker+'\nFILE *OpenPLLTraceFile = NULL;')
            # Redirect all contribution and identity records, retaining native errors on stderr.
            start=text.index('void\nOpenPLLTraceGround(');stop=text.index('NodeRegion *\nextBasic(',start)
            text=text[:start]+text[start:stop].replace('fprintf(stderr,','fprintf(OpenPLLTraceFile,')+text[stop:]
            for marker in ['fprintf(stderr, "OPENPLL_BEGIN','fprintf(stderr, "OPENPLL_ID']:
                assert text.count(marker)==1;text=text.replace(marker,marker.replace('stderr','OpenPLLTraceFile'))
            marker='''    if (OpenPLLTraceEnabled)
    {
        if (!(ExtOptions & EXT_DOCAPACITANCE)''';assert text.count(marker)==1
            text=text.replace(marker,'''    if (OpenPLLTraceEnabled)
    {
        const char *openpll_path = getenv("OPENPLL_CAP_TRACE_FILE");
        if (!openpll_path || OpenPLLTraceFile != NULL)
        {
            fprintf(stderr, "OPENPLL_TRACE requires a private file and one active cell\\n");
            exit(2);
        }
        OpenPLLTraceFile = fopen(openpll_path, "wx");
        if (!OpenPLLTraceFile) { perror("OPENPLL_TRACE private file"); exit(2); }
        if (!(ExtOptions & EXT_DOCAPACITANCE)''')
            marker='    ExtFreeLabRegions((LabRegion *) transList);\n    return (nodeList);';assert text.count(marker)==1
            text=text.replace(marker,'''    if (OpenPLLTraceEnabled)
    {
        fprintf(OpenPLLTraceFile, "OPENPLL_END\\n");
        if (fclose(OpenPLLTraceFile) != 0) { perror("OPENPLL_TRACE close"); exit(2); }
        OpenPLLTraceFile = NULL;
    }
'''+marker)
        else:
            # extCouple calls helper functions in ExtBasic, so no file handle needed here.
            assert text==(prior.parent/('patched_'+name)).read_text()
        (out/('original_'+name)).write_text(original);(out/('patched_'+name)).write_text(text)
        patch+=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/extract/'+name,tofile='b/extract/'+name))
        p.write_text(text);diagnostic[str(p)]=sha(p)
    (out/'change.patch').write_text(patch)
    paths=[Path(__file__).resolve(),prior,base/'DCO_full_C_trace_controls_001/failure.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir()},diagnostic_source_files=diagnostic,
        private_exclusive_trace_file=True,explicit_trace_end_marker=True,
        full_geometry_used=True,native_capacitance_arithmetic_statements_retained=True,
        release_qualified=False,adopted=False))
    print('Private-file tracer patch prepared; native controls still required.')


if __name__=='__main__':main()
