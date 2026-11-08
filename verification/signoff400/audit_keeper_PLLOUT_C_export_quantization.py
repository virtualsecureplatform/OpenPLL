"""Reconcile literal PLLOUT EXT/SPICE capacitance export; no dynamic accuracy claim."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from native_spice_comments import strip_floating_annotation
from audit_keeper_native_R_contraction import number


def reconcile(native,printed):
    if set(native)!=set(printed):raise ValueError('one-to-one coupling endpoint inventory required')
    if any(v<0 for v in printed.values()):raise ValueError('nonnegative printed capacitances required')
    negative=[k for k in native if native[k]<0]
    if any(printed[k]!=0 or abs(native[k])>=F(1,10**18) for k in negative):raise ValueError('unqualified negative native coupling')
    negative_zeroed=sum((native[k] for k in negative),F(0))
    zeroed=[k for k in native if native[k]>0 and printed[k]==0]
    if any(native[k]>=F(1,10**18) for k in zeroed):raise ValueError('zeroed coupling exceeds observed sub-attofarad formatter class')
    positive=[k for k in native if printed[k]>0];loss=sum((native[k] for k in zeroed),F(0));rounding=sum((printed[k]-native[k] for k in positive),F(0));total_native=sum(native.values(),F(0));total_printed=sum(printed.values(),F(0))
    if total_native-total_printed!=loss+negative_zeroed-rounding:raise ValueError('unexplained capacitance export discrepancy')
    return dict(native_negative_pairs_printed_zero=len(negative),signed_negative_native_C_F_exact=str(negative_zeroed),signed_negative_native_C_F=float(negative_zeroed),coupling_pairs=len(native),positive_native_couplings_printed_zero=len(zeroed),positive_printed_couplings=len(positive),native_zero_pairs=sum(v==0 for v in native.values()),zeroed_positive_C_F_exact=str(loss),zeroed_positive_C_fF=float(loss*10**15),maximum_zeroed_positive_C_aF=float(max((native[k] for k in zeroed),default=F(0))*10**18),positive_printed_rounding_delta_F_exact=str(rounding),positive_printed_rounding_delta_fF=float(rounding*10**15),native_coupling_fF=float(total_native*10**15),printed_coupling_fF=float(total_printed*10**15),coupling_endpoint_inventory_matches=True,exact_total_discrepancy_reconciled=True,dynamic_frequency_or_timing_error_qualified=False,release_ready=False)


def run(flat,source,output):
    receipt=flat/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts']);ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';spice=flat/'capacitance.spice';native={};printed={};ground=F(0)
    with ext.open() as stream:
        for line in stream:
            if not line.startswith('cap ') or '"PLLOUT"' not in line:continue
            n,m,v=re.fullmatch(r'cap "([^\"]*)" "([^\"]*)" (\S+)\s*',line).groups();other=m if n=='PLLOUT' else n;key=other.replace('/','.').lower();native[key]=native.get(key,F(0))+F(v)*F(1,10**18)
    with spice.open() as stream:
        for line in stream:
            if line[:1].upper()!='C' or 'PLLOUT' not in line.split()[1:3]:continue
            _,n,m,v=strip_floating_annotation(line).split();other=m if n=='PLLOUT' else n;key=other.lower()
            if key=='vgnd':ground+=number(v)
            else:printed[key]=printed.get(key,F(0))+number(v)
    result=reconcile(native,printed);output.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in [receipt,ext,spice,source,Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py'),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**result,printed_ground_C_fF=float(ground*10**15),scope='literal EXT/SPICE export accounting only; source formatter inspected separately; upstream dependency closures not requalified'))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','source','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.flat.resolve(),a.source.resolve(),a.output.resolve())
