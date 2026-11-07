.side_set 1
.wrap_target
bitLoop:
    out x, 1        side 0 [2]
    jmp !x doZero   side 1 [2]
    jmp bitLoop     side 1 [3]
doZero:
    nop             side 0 [3]
.wrap
