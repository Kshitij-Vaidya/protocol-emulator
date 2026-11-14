idle:
    jmp pin checkTx
    set x, 9
rxBit:
    wait 1 gpio 3
    wait 0 gpio 3
    in pins, 1
    jmp x-- rxBit
    push
    wait 1 gpio 3
    jmp idle
checkTx:
    mov x, status
    set y, 1
    and x, y
    jmp !x send
    jmp idle
send:
    pull
    mov osr, ~osr
    set pindirs, 2
    set x, 7
holdClock:
    jmp x-- holdClock  [15]
    set pindirs, 3
    set pindirs, 1
    set x, 9
txBit:
    wait 0 gpio 3
    out pindirs, 1
    wait 1 gpio 3
    jmp x-- txBit
    wait 0 gpio 3
    mov x, pins
    set y, 1
    and x, y
    jmp !x acked
    flag set 2
acked:
    wait 1 gpio 3
    wait 1 gpio 2
