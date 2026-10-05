#!/usr/bin/env python3
"""Play Nextion commands into the emulator over its USB (UART0), as the Teensy would.
   usage: nextion_send.py [port] — runs a FrontView-like sequence, then reads back a value."""
import serial, sys, time
port = sys.argv[1] if len(sys.argv) > 1 else '/dev/cu.usbserial-11130'
s = serial.Serial(port, 921600, timeout=0.3)
def cmd(c): s.write(c.encode('latin1') + b'\xff\xff\xff'); time.sleep(0.02)
s.setDTR(False); s.setRTS(False); time.sleep(3.5)   # opening the port auto-resets the board: let it boot
cmd('page FrontView')
cmd('ModelName.txt="Black Thunder 2"')
cmd('t0.txt="Bank 1"'); cmd('n0.val=79'); cmd('n1.val=1234'); cmd('vis t1,0')
cmd('Vcc.txt="7.9V"'); cmd('RXV.txt="24.1V"')
for v in range(0, 100, 7): cmd(f'n0.val={v}'); time.sleep(0.05)
cmd('get n0.val'); r = s.read(8); print('get n0.val ->', r.hex(), '(expect 71 + int32 + ffffff)')
cmd('get ModelName.txt'); r = s.read(40); print('get ModelName.txt ->', r)
cmd('page RatesView'); cmd('Ail.val=100'); cmd('Ele.val=90'); cmd('Rud.val=110')
cmd('sendme'); r = s.read(5); print('sendme ->', r.hex())
cmd('page FrontView')
print('done')
