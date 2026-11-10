.side_set 1
    set pins, 1        side 0
.wrap_target
    pull               side 0
    set pins, 0        side 0
    set x, 7           side 0
bitLoop:
    out pins, 1        side 0 [1]
    in pins, 1         side 1
    jmp x-- bitLoop    side 1
    push               side 0
    set pins, 1        side 0
.wrap
