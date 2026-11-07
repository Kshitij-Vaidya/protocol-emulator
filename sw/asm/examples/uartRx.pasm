start:
    wait 0 pin 0
    set x, 7           [10]
bitLoop:
    in pins, 1
    jmp x-- bitLoop    [6]
    jmp pin goodStop
    flag set 0
    wait 1 pin 0
    jmp start
goodStop:
    push
