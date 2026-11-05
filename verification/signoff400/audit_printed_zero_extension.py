"""Independently inventory printed zero-extension nodes and their native types."""
import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import time
from common import save, sha
from resources import lease


def run(comparison, output):
    comparison, out = comparison.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proof = comparison/'assessment.json'
    source = json.loads(proof.read_text())
    if not source['full_printed_native_matrix_reconstruction_verified']:
        raise ValueError('complete printed-native comparison required')
    ledger = Path(source['explicit_zero_extension_node_map'])
    ext = next(Path(p) for p in source['input_sha256']
               if p.endswith('Prototype400_FilledCapacitanceView.ext'))
    paths = [proof, ledger, ext, Path(__file__).resolve()]
    with lease(1,4,deadline):
        pins = {str(p):sha(p) for p in paths}
        if pins[str(ledger)]!=source['artifacts'][str(ledger)] or pins[str(ext)]!=source['input_sha256'][str(ext)]:
            raise ValueError('zero-extension source changed')
        counts = source['complete_printed_record_counts']
        wanted = {}
        with ledger.open() as stream:
            prior_name = None
            for line in stream:
                number,name = json.loads(line)
                if number!=counts['known_conductor_nodes']+len(wanted) or (prior_name is not None and name<=prior_name):
                    raise ValueError('noncontiguous or unsorted zero-extension identity')
                wanted[name]=number
                prior_name=name
        if len(wanted)!=counts['explicit_zero_extension_nodes']:
            raise ValueError('complete zero-extension ledger required')
        found,types = {},Counter()
        with ext.open() as stream:
            for lineno,line in enumerate(stream):
                if lineno%100000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                    raise TimeoutError('zero-extension audit deadline')
                if not line.startswith('node "'):
                    continue
                _,name,tail = line.split('"',2)
                if name not in wanted:
                    continue
                fields = tail.split()
                if name in found or len(fields)<5 or Fraction(fields[1])!=0:
                    raise ValueError('zero-extension node is duplicate, malformed or nonzero')
                found[name]=[wanted[name],name,int(fields[2]),int(fields[3]),fields[4]]
                types[fields[4]]+=1
        if found.keys()!=wanted.keys():
            raise ValueError('printed zero-extension node missing')
        inventory = out/'nodes.jsonl'
        with inventory.open('w') as stream:
            for name in sorted(found):
                stream.write(json.dumps(found[name])+'\n')
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('zero-extension input changed during independent inventory')
        save(out/'assessment.json',dict(input_sha256=pins,
             artifacts={str(inventory):sha(inventory)},
             every_zero_extension_printed_node_independently_rechecked=True,
             explicit_zero_nodes=len(found),native_printed_type_counts=dict(types),
             no_printed_coupling_endpoints_proven_by_controlled_parent_parser=True,
             independent_coupling_endpoint_audit=False,
             physical_fill_material_model_qualified=False,
             physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(explicit_zero_nodes=len(found),native_printed_type_counts=dict(types))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.comparison,args.output)
