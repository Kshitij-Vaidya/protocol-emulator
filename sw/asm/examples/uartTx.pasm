.side_set 1 opt
    pull        side 1 [3]
    set x, 7    side 0 [3]
bitLoop:
    out pins, 1
    jmp x-- bitLoop    [2]
