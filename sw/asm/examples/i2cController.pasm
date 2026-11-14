.side_set 1 opt pindirs
    set t, 63
    set pindirs, 0
.wrap_target
nextWord:
    pull
    mov osr, ~osr
    out x, 1
    jmp x-- byteStart
    jmp pin startHigh
    set pindirs, 2     [3]
    set pindirs, 0     [3]
startHigh:
    wait 1 gpio 1 timeout
    jmp timeout busError [2]
    set pindirs, 1     [3]
    set pindirs, 3     [3]
byteStart:
    out y, 1
    set x, 8
bitLoop:
    out pindirs, 1     side 1 [3]
    nop                side 1 [3]
    nop                side 0
    wait 1 gpio 1 timeout
    jmp timeout busError
    in pins, 1         [1]
    jmp x-- bitLoop
    push               side 1 [3]
    jmp y-- nextWord
    set pindirs, 3     [3]
    set pindirs, 1     [3]
    wait 1 gpio 1 timeout
    jmp timeout busError [2]
    set pindirs, 0     [3]
    nop                [3]
.wrap
busError:
    flag set 1
errorLoop:
    jmp errorLoop
