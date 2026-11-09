"""Build an 80 ns-reset diagnostic capture; this is not a qualified lock stimulus."""
from run_keeper_native_BSIM_coarse_band import transient_deck as previous_deck
from reset_contract_v4 import validate_assertion


def transient_deck(text,capture,fine,coarse,max_step_ps=10):
    validate_assertion(0,80,reference_running=True,programming_static=True)
    lines=text.splitlines()
    enable=[s.split() for s in lines if len(s.split())==4 and s.split()[1]=='PLL_ENABLE']
    if len(enable)!=1 or enable[0][2:]!=['0','0']:
        raise ValueError('one held-disabled PLL_ENABLE source required')
    result,ports=previous_deck(text,capture,fine,coarse,max_step_ps)
    replacements={f'.tran 10p 260n 0 {max_step_ps}p':f'.tran 10p 340n 0 {max_step_ps}p',
                  'VRESET RESET_N 0 PWL(0 0 5n 0 5.1n 1.8 260n 1.8)':
                  'VRESET RESET_N 0 PWL(0 0 80n 0 80.1n 1.8 340n 1.8)',
                  '.print tran format=raw precision=17 file='+str(capture)+' V(*)':
                  '.print tran format=std precision=17 file='+str(capture)+' V(*)'}
    for old,new in replacements.items():
        if result.splitlines().count(old)!=1:raise ValueError('unique checked deck statement required')
        result=result.replace(old,new)
    return result,ports
