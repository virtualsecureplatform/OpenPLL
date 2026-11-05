#!/usr/bin/env python3
"""Record native R-node reasons and incident material types without changing R/C.

Native .res.ext prints a temporary zero instead of actual node type. Preserve
that output and log additional node and incident resistor metadata to a private
exclusive stream. This is diagnostic support evidence, not a physical model.
"""
from pathlib import Path
import difflib,subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

HELPER=r'''
/* Opt-in native R-node provenance; no extraction or output arithmetic changes. */
static FILE *OpenPLLRNodeFile = NULL;
static unsigned long OpenPLLRNodeGroup = 0;

static unsigned long
OpenPLLRNodeBegin(const char *original)
{
    const char *path = getenv("OPENPLL_R_NODE_TRACE_FILE");
    int type;
    if (!path) return 0;
    if (!OpenPLLRNodeFile)
    {
        OpenPLLRNodeFile = fopen(path, "wx");
        if (!OpenPLLRNodeFile) { perror("OPENPLL_R_NODE_TRACE_FILE"); exit(2); }
        for (type = 0; type < TT_MAXTYPES; type++)
            if (DBTypeLongName(type))
                fprintf(OpenPLLRNodeFile, "TYPE %d \"%s\"\n", type, DBTypeLongName(type));
    }
    OpenPLLRNodeGroup++;
    fprintf(OpenPLLRNodeFile, "BEGIN %lu \"%s\"\n", OpenPLLRNodeGroup, original);
    return OpenPLLRNodeGroup;
}

static void
OpenPLLRNodeRecord(unsigned long group, resNode *node)
{
    resElement *incident;
    if (!group) return;
    fprintf(OpenPLLRNodeFile, "NODE %lu %p \"%s\" %d %d %u %d\n", group,
        (void *)node, node->rn_name, node->rn_loc.p_x, node->rn_loc.p_y,
        node->rn_why, node->rn_status);
    for (incident = node->rn_re; incident; incident = incident->re_nextEl)
    {
        resResistor *res = incident->re_thisEl;
        fprintf(OpenPLLRNodeFile, "EDGE %lu %p %p %p %.17g %u %d\n", group,
            (void *)node, (void *)res->rr_node[0], (void *)res->rr_node[1],
            (double)res->rr_value, (unsigned)res->rr_tt, res->rr_status);
    }
}

static void
OpenPLLRNodeEnd(unsigned long group)
{
    if (!group) return;
    fprintf(OpenPLLRNodeFile, "END %lu\n", group);
    if (fflush(OpenPLLRNodeFile) != 0 || ferror(OpenPLLRNodeFile))
    { perror("OPENPLL_R_NODE_TRACE flush"); exit(2); }
}
'''


def main():
    base=ROOT/'build/timing400/release_001';source=ROOT/'build/timing400/magic_location_source_001'
    prior=base/'magic_RC_substrate_C_patch_001/assessment.json';v=verify(prior)
    for p,d in v['diagnostic_source_files'].items():assert sha(p)==d,p
    name='resis/ResPrint.c';p=source/name
    original=subprocess.check_output(['git','-C',str(source),'show','8.3.623:'+name],text=True)
    assert p.read_text()==original
    text=original.replace('#include <stdio.h>','#include <stdio.h>\n#include <stdlib.h>',1)
    marker='void\nResPrintExtNode(outextfile, nodelist, node)';assert text.count(marker)==1
    text=text.replace(marker,HELPER+'\n'+marker)
    marker='    resNode\t*snode;\n';start=text.index('void\nResPrintExtNode(');at=text.index(marker,start)
    text=text[:at]+text[at:].replace(marker,marker+'    unsigned long openpll_group = OpenPLLRNodeBegin(nodename);\n',1)
    marker='''\t\t    /* the following is TEMPORARILY set to 0 */
\t\t    0);
\t}
    }

    if (NeedFix)''';assert text.count(marker)==1
    text=text.replace(marker,'''\t\t    /* the following is TEMPORARILY set to 0 */
\t\t    0);
\t}
        OpenPLLRNodeRecord(openpll_group, snode);
    }
    OpenPLLRNodeEnd(openpll_group);

    if (NeedFix)''')
    out=base/'magic_R_node_trace_patch_001';out.mkdir(exist_ok=False)
    (out/'original_ResPrint.c').write_text(original);(out/'patched_ResPrint.c').write_text(text)
    patch=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
    # Preserve the entire cumulative diagnostic patch for a clean rebuild.
    for file in ['extract/ExtBasic.c','extract/ExtCouple.c','extract/ExtCell.c']:
        native=subprocess.check_output(['git','-C',str(source),'show','8.3.623:'+file],text=True)
        patched=(source/file).read_text();(out/('patched_'+Path(file).name)).write_text(patched)
        patch+=''.join(difflib.unified_diff(native.splitlines(True),patched.splitlines(True),fromfile='a/'+file,tofile='b/'+file))
    p.write_text(text);(out/'change.patch').write_text(patch)
    files=[source/f for f in ['resis/ResPrint.c','extract/ExtBasic.c','extract/ExtCouple.c','extract/ExtCell.c']]
    paths=[Path(__file__).resolve(),prior,base/'DCO_native_R_node_geometry_002/assessment.json',source/'resis/resis.h']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(p):sha(p) for p in files},private_exclusive_R_provenance_stream=True,
        native_R_C_arithmetic_and_native_output_statements_unchanged=True,node_reason_and_incident_materials_logged=True,
        native_controls_required=True,spatial_RC_or_transient_error_qualified=False,release_qualified=False,adopted=False))
    print('Prepared native R-node provenance tracer; unchanged-output controls required.')


if __name__=='__main__':main()
