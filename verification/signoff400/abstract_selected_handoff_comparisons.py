"""Sound equality abstraction: exact selected fields AND unconstrained other equality.

For each original trace, choose the new input to equal omitted-field equality.
Then every original comparison result and state transition is reproduced.
"""
import copy


def abstract(design,seed_bit):
    if seed_bit not in range(8):raise ValueError('one of eight fine-seed bits required')
    result=copy.deepcopy(design);m=result['modules']['IntegerPLL_ProgrammedCore'];cells=m['cells'];nets=m['netnames']
    bits=[b for c in cells.values() for values in c['connections'].values() for b in values if isinstance(b,int)];next_bit=max(bits)+1
    kept=[13,20+seed_bit,*range(28,34)];omitted=sorted(set(range(34))-set(kept));records=[]
    def width(n):return format(n,'032b')
    def logic(kind,connections,widths):
        return dict(type=kind,parameters={**{k:width(v) for k,v in widths.items()},**({'A_SIGNED':width(0),'B_SIGNED':width(0)} if kind in ('$eq','$and') else {'A_SIGNED':width(0)} if kind=='$not' else {})},attributes={},port_directions={k:'output' if k=='Y' else 'input' for k in connections},connections=connections)
    for name,c in list(cells.items()):
        if c['type'] not in ('$eq','$ne') or int(c['parameters']['A_WIDTH'],2)!=34:continue
        leaf=next((n for n in ('handoff','gen_feedback_handoff.fine_handoff') if name.startswith('$flatten\\'+n+'.')),None)
        if leaf is None or int(c['parameters']['B_WIDTH'],2)!=34 or len(c['connections']['Y'])!=1:raise ValueError('only selected 34-bit command comparisons allowed')
        a,b,y=(c['connections'][n] for n in ('A','B','Y'));expected=[nets[leaf+'.payload']['bits'],nets[leaf+'.COMMAND']['bits']]
        if not ((a==expected[0] and b==expected[1]) or (a==expected[1] and b==expected[0])):raise ValueError('comparison must be actual payload against actual command')
        eq,other,combined=range(next_bit,next_bit+3);next_bit+=3;prefix=f'$openpll_compare_{len(records)}'
        if any(n.startswith(prefix) for n in cells):raise ValueError('abstraction cell name collision')
        cells[prefix+'_kept']=logic('$eq',{'A':[a[i] for i in kept],'B':[b[i] for i in kept],'Y':[eq]},{'A_WIDTH':8,'B_WIDTH':8,'Y_WIDTH':1})
        cells[prefix+'_other']=dict(type='$anyseq',parameters={'WIDTH':width(1)},attributes={},port_directions={'Y':'output'},connections={'Y':[other]})
        conjunction=logic('$and',{'A':[eq],'B':[other],'Y':y if c['type']=='$eq' else [combined]},{'A_WIDTH':1,'B_WIDTH':1,'Y_WIDTH':1})
        if c['type']=='$eq':cells[name]=conjunction
        else:
            cells[prefix+'_combined']=conjunction;cells[name]=logic('$not',{'A':[combined],'Y':y},{'A_WIDTH':1,'Y_WIDTH':1})
        records.append(dict(original_cell=name,original_type=c['type'],handshake=leaf,kept_bit_indices=kept,omitted_bit_indices=omitted,extra_equality_output_bit=other,original_A=a,original_B=b,original_Y=y))
    if len(records)!=4 or sorted(r['handshake'] for r in records)!=['gen_feedback_handoff.fine_handoff']*2+['handoff']*2:raise ValueError('exactly four selected command comparisons required')
    return result,records
