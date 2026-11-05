"""Generate local noninverting data-buffer ECOs; final timing remains mandatory."""


def actions_for_plan(targets):
    if not targets or len({(t['capture_cell'], t['capture_pin']) for t in targets}) != len(targets):
        raise ValueError('unique measured capture cells required')
    result = []
    for index, target in enumerate(targets):
        name = target['capture_cell']
        count = target['buffers']
        if target.get('capture_pin') not in {'D', 'A', 'B', 'A1', 'A2', 'B1', 'B2'}:
            raise ValueError('explicit measured data or logic receiver pin required')
        if any(c in name for c in '{}\\\n\r') or not isinstance(count, int) or not 1 <= count <= 8:
            raise ValueError('invalid bounded interstage repair')
        result.append(f'''set sink [$block findInst {{{name}}}]
if {{$sink eq {{NULL}}}} {{error "measured interstage sink absent"}}
if {{[[$sink getMaster] getName] ne {{{target['capture_master']}}}}} {{error "capture master changed"}}
set data [$sink findITerm {target["capture_pin"]}]
set upstream [$data getNet]
if {{$upstream eq {{NULL}}}} {{error "interstage data disconnected"}}
lassign [$sink getLocation] sx sy
set orient [$sink getOrient]
''')
        for stage in range(count):
            prefix = f'prototype_selective_hold_{index}_{stage}'
            result.append(f'''set buffer [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__clkbuf_2] {prefix}]
$buffer setOrient $orient
$buffer setLocation $sx $sy
$buffer setPlacementStatus PLACED
set local [odb::dbNet_create $block {prefix}_net]
[$buffer findITerm A] connect $upstream
[$buffer findITerm X] connect $local
foreach pin {{VPWR VPB}} {{[$buffer findITerm $pin] connect [$block findNet VDD]}}
foreach pin {{VGND VNB}} {{[$buffer findITerm $pin] connect [$block findNet VSS]}}
if {{[$upstream getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$upstream getWire]}}
set upstream $local
''')
        result.append('$data connect $upstream\n')
    return ''.join(result)
