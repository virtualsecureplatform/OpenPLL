import json,re
import numpy as np
def audit(text,folder,kind,variant,flavor,label_run,threads,policy,expected_scopes,original,n,diag,native_rhs,known_rhs,remaining):
 cases=[json.loads(line) for line in text.splitlines() if line.startswith('{')];assert len(cases)==(5 if kind=='rhs' else 8)
 totals=re.findall(r'OpenPLL_inner_totals calls=(\d+) seconds=(\S+)',text);assert len(totals)==1
 if threads:assert f'threads={threads} policy={policy}' in text
 checks=[]
 for case in cases:
  remaining();label=case['case'];solution=np.fromfile(folder/(label+'.bin'),dtype='<f8');rhs=np.fromfile(folder/(label+'.rhs.bin'),dtype='<f8')
  assert case['original_Jacobian_unchanged'] and case['original_RHS_unchanged'];assert solution.shape==rhs.shape==(n,) and np.isfinite(solution).all()
  M=original.copy()
  if kind=='matrix':
   step=int(label.rsplit('step',1)[1]);delta=[0,1e-8,1e-6,1e-4,.01,0,.01,0][step]
   M.data[diag]+=delta*abs(M.data[diag]);
   if step==6:M.data*=2
   known=.1*(np.sin(.013*np.arange(n)+.0001*step)+np.cos(.027*np.arange(n)))
   expected=M@known;terms=np.diff(M.indptr);eps=np.finfo(float).eps;bound=8*(terms*eps/(1-terms*eps))*(abs(M)@abs(known))+8*eps*abs(expected)
   assert np.all(abs(rhs-expected)<=bound);assert max(abs(solution-known))<1e-7
  else:
   expected=known_rhs if label.endswith(('known_solution','known_repeat')) else native_rhs.copy()
   if label.endswith('perturbed_native'):
    scale=1/np.asarray(abs(M).max(axis=1).toarray()).ravel()
    expected+=.001*np.linalg.norm(scale*native_rhs)/np.linalg.norm(scale*known_rhs)*known_rhs
   if label.endswith('perturbed_native'):
    perturbation=expected-native_rhs
    eps=np.finfo(float).eps
    bound=8*n*eps*abs(perturbation)+8*eps*(abs(native_rhs)+abs(perturbation))
    assert np.all(abs(rhs-expected)<=bound)
   else:assert np.array_equal(rhs,expected)
  scale=1/np.asarray(abs(M).max(axis=1).toarray()).ravel();relative=float(np.linalg.norm(scale*(M@solution-rhs))/np.linalg.norm(scale*rhs));assert relative<=1e-12
  checks.append(dict(case=label,weighted_original_equation_residual=relative,solve_wall_s=case['solve_wall_s']))
 report=dict(label=label_run,flavor=flavor,variant=variant,kind=kind,checks=checks,solve_total_s=sum(v['solve_wall_s'] for v in cases),inner_calls=int(totals[0][0]),inner_seconds=float(totals[0][1]),stale_factor_recovery_exercised='OpenPLL_wire_factor_refresh_after_nonpass' in text)
 if flavor=='coarse':
  phase=next(line for line in text.splitlines() if line.startswith('solve_profile '))
  report['api_phase_profile']={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',phase)}
  kernels=next(line for line in text.splitlines() if line.startswith('klu_phase_profile '))
  report['vendor_kernel_profile']={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',kernels)}
  coarse=[]
  for line in text.splitlines():
   if line.startswith('kls_coarse slot='):
    pairs=dict(re.findall(r'(\w+)=([^ ]+)',line));coarse.append({k:(v if k in ('name','role') else int(v)) for k,v in pairs.items()})
  assert len(coarse)==expected_scopes and 'kls_coarse_summary errors=0' in text
  report['coarse_scopes']=coarse
 return report
