# gw.py
#
# Greaseweazle control script.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import crcmod.predefined
import sys, struct, argparse, serial, collections
from timeit import default_timer as timer

from greaseweazle import version

# 40MHz
scp_freq = 40000000

BAUD_CLEAR_COMMS    = 10000
BAUD_NORMAL         = 9600

CMD_GET_INFO        = 0
CMD_SEEK            = 1
CMD_SIDE            = 2
CMD_SET_DELAYS      = 3
CMD_GET_DELAYS      = 4
CMD_MOTOR           = 5
CMD_READ_FLUX       = 6
CMD_WRITE_FLUX      = 7
CMD_GET_FLUX_STATUS = 8
CMD_GET_READ_INFO   = 9

# Bootloader-specific:
CMD_UPDATE          = 1

ACK_OKAY            = 0
ACK_BAD_COMMAND     = 1
ACK_NO_INDEX        = 2
ACK_NO_TRK0         = 3
ACK_FLUX_OVERFLOW   = 4
ACK_FLUX_UNDERFLOW  = 5
ACK_WRPROT          = 6
ACK_MAX             = 6

ack_str = [
  "Okay", "Bad Command", "No Index", "Track 0 not found",
  "Flux Overflow", "Flux Underflow", "Disk is Write Protected" ]

class CmdError(Exception):
  def __init__(self, cmd, code):
    self.cmd = cmd
    self.code = code
  def __str__(self):
    if self.code <= ACK_MAX:
      return ack_str[self.code]
    return "Unknown Error (%u)" % self.code

def send_cmd(cmd):
  ser.write(cmd)
  (c,r) = struct.unpack("2B", ser.read(2))
  assert c == cmd[0]
  if r != 0:
    raise CmdError(c,r)

def get_fw_info():
  send_cmd(struct.pack("3B", CMD_GET_INFO, 3, 0))
  x = struct.unpack("<4BI24x", ser.read(32))
  return x

def print_fw_info(info):
  (major, minor, max_revs, max_cmd, freq) = info
  print("Greaseweazle v%u.%u" % (major, minor))
  print("Max revs %u" % (max_revs))
  print("Max cmd %u" % (max_cmd))
  print("Sample frequency: %.2f MHz" % (freq / 1000000))
  
def seek(cyl, side):
  send_cmd(struct.pack("3B", CMD_SEEK, 3, cyl))
  send_cmd(struct.pack("3B", CMD_SIDE, 3, side))

def get_delays():
  send_cmd(struct.pack("2B", CMD_GET_DELAYS, 2))
  return struct.unpack("<4H", ser.read(4*2))
  
def print_delays(x):
  (step_delay, seek_settle, motor_delay, auto_off) = x
  print("Step Delay: %ums" % step_delay)
  print("Settle Time: %ums" % seek_settle)
  print("Motor Delay: %ums" % motor_delay)
  print("Auto Off: %ums" % auto_off)

def set_delays(step_delay = None, seek_settle = None,
               motor_delay = None, auto_off = None):
  (_step_delay, _seek_settle, _motor_delay, _auto_off) = get_delays()
  if not step_delay: step_delay = _step_delay
  if not seek_settle: seek_settle = _seek_settle
  if not motor_delay: motor_delay = _motor_delay
  if not auto_off: auto_off = _auto_off
  send_cmd(struct.pack("<2B4H", CMD_SET_DELAYS, 10,
                            step_delay, seek_settle, motor_delay, auto_off))

def motor(state):
  send_cmd(struct.pack("3B", CMD_MOTOR, 3, int(state)))

def get_read_info():
  send_cmd(struct.pack("2B", CMD_GET_READ_INFO, 2))
  x = []
  for i in range(7):
    x.append(struct.unpack("<2I", ser.read(2*4)))
  return x

def print_read_info(info):
  for (time, samples) in info:
    print("%u ticks, %u samples" % (time, samples))

def write_flux(flux):
  start = timer()
  x = bytearray()
  for val in flux:
    if val == 0:
      pass
    elif val < 250:
      x.append(val)
    else:
      high = val // 250
      if high <= 5:
        x.append(249+high)
        x.append(1 + val%250)
      else:
        x.append(255)
        x.append(1 | (val<<1) & 255)
        x.append(1 | (val>>6) & 255)
        x.append(1 | (val>>13) & 255)
        x.append(1 | (val>>20) & 255)
  x.append(0) # End of Stream
  end = timer()
  #print("%u flux -> %u bytes in %f seconds" % (len(flux), len(x), end-start))
  retry = 0
  while True:
    start = timer()
    send_cmd(struct.pack("2B", CMD_WRITE_FLUX, 2))
    ser.write(x)
    ser.read(1) # Sync with Greaseweazle
    try:
      send_cmd(struct.pack("2B", CMD_GET_FLUX_STATUS, 2))
    except CmdError as error:
      if error.code == ACK_FLUX_UNDERFLOW and retry < 5:
        retry += 1
        print("Retry #%u..." % retry)
        continue;
      raise
    end = timer()
    #print("Track written in %f seconds" % (end-start))
    break
  
def read_flux(nr_revs):
  retry = 0
  while True:
    start = timer()
    x = collections.deque()
    send_cmd(struct.pack("3B", CMD_READ_FLUX, 3, nr_revs))
    nr = 0
    while True:
      x += ser.read(1)
      x += ser.read(ser.in_waiting)
      nr += 1;
      if x[-1] == 0:
        break
    try:
      send_cmd(struct.pack("2B", CMD_GET_FLUX_STATUS, 2))
    except CmdError as error:
      if error.code == ACK_FLUX_OVERFLOW and retry < 5:
        retry += 1
        print("Retry #%u..." % retry)
        del x
        continue;
      raise
    end = timer()
    break
    
  #print("Read %u bytes in %u batches in %f seconds" % (len(x), nr, end-start))

  start = timer()
  y = []
  while x:
    i = x.popleft()
    if i < 250:
      y.append(i)
    elif i == 255:
      val =  (x.popleft() & 254) >>  1
      val += (x.popleft() & 254) <<  6
      val += (x.popleft() & 254) << 13
      val += (x.popleft() & 254) << 20
      y.append(val)
    else:
      val = (i - 249) * 250
      val += x.popleft() - 1
      y.append(val)
  assert y[-1] == 0
  y = y[:-1]
  end = timer()

  #print("Processed %u flux values in %f seconds" % (len(y), end-start))

  return y

def read(args):
  factor = scp_freq / sample_freq
  trk_dat = bytearray()
  trk_offs = []
  if args.single_sided:
    track_range = range(args.scyl, args.ecyl+1)
    nr_sides = 1
  else:
    track_range = range(args.scyl*2, (args.ecyl+1)*2)
    nr_sides = 2
  for i in track_range:
    cyl = i >> (nr_sides - 1)
    side = i & (nr_sides - 1)
    print("\rReading Track %u.%u..." % (cyl, side), end="")
    trk_offs.append(len(trk_dat))
    seek(cyl, side)
    flux = read_flux(args.revs)
    info = get_read_info()[:args.revs]
    #print_read_info(info)
    trk_dat += struct.pack("<3sB", b"TRK", i)
    dat_off = 4 + args.revs*12
    for (time, samples) in info:
      time = int(round(time * factor))
      trk_dat += struct.pack("<III", time, samples, dat_off)
      dat_off += samples * 2
    rem = 0.0
    for x in flux:
      y = x * factor + rem
      val = int(round(y))
      rem = y - val
      while val >= 65536:
        trk_dat.append(0)
        trk_dat.append(0)
        val -= 65536
      if val == 0:
        val = 1
      trk_dat.append(val>>8)
      trk_dat.append(val&255)
  print()
  csum = 0
  for x in trk_dat:
    csum += x
  trk_offs_dat = bytearray()
  for x in trk_offs:
    trk_offs_dat += struct.pack("<I", 0x2b0 + x)
  trk_offs_dat += bytes(0x2a0 - len(trk_offs_dat))
  for x in trk_offs_dat:
    csum += x
  ds_flag = 0
  if args.single_sided:
    ds_flag = 1
  header_dat = struct.pack("<3s9BI",
                           b"SCP",    # Signature
                           0,         # Version
                           0x80,      # DiskType = Other
                           args.revs, # Nr Revolutions
                           track_range.start, # Start track
                           track_range.stop-1, # End track
                           0x01,      # Flags = Index
                           0,         # 16-bit cell width
                           ds_flag,   # Double Sided
                           0,         # 25ns capture
                           csum & 0xffffffff)
  with open(args.file, "wb") as f:
    f.write(header_dat)
    f.write(trk_offs_dat)
    f.write(trk_dat)

def write(args):
  factor = sample_freq / scp_freq
  with open(args.file, "rb") as f:
    dat = f.read()
  header = struct.unpack("<3s9BI", dat[0:16])
  assert header[0] == b"SCP"
  trk_offs = struct.unpack("<168I", dat[16:0x2b0])
  if args.single_sided:
    track_range = range(args.scyl, args.ecyl+1)
    nr_sides = 1
  else:
    track_range = range(args.scyl*2, (args.ecyl+1)*2)
    nr_sides = 2
  for i in track_range:
    cyl = i >> (nr_sides - 1)
    side = i & (nr_sides - 1)
    print("\rWriting Track %u.%u..." % (cyl, side), end="")
    if trk_offs[i] == 0:
      continue
    seek(cyl, side)
    thdr = struct.unpack("<3sBIII", dat[trk_offs[i]:trk_offs[i]+16])
    (sig,_,_,samples,off) = thdr
    assert sig == b"TRK"
    tdat = dat[trk_offs[i]+off:trk_offs[i]+off+samples*2]
    flux = []
    rem = 0.0
    for i in range(0,len(tdat),2):
      x = tdat[i]*256 + tdat[i+1]
      if x == 0:
        rem += 65536.0
        continue
      y = x * factor + rem
      val = int(round(y))
      rem = y - val
      flux.append(val)
    write_flux(flux)
  print()

def update(args):
  with open(args.file, "rb") as f:
    dat = f.read()
  (sig, maj, min, pad1, pad2, crc) = struct.unpack(">2s4BH", dat[-8:])
  if len(dat) & 3 != 0 or sig != b'GW' or pad1 != 0 or pad2 != 0:
    print("%s: Bad update file" % (args.file))
    return
  crc16 = crcmod.predefined.Crc('crc-ccitt-false')
  crc16.update(dat)
  if crc16.crcValue != 0:
    print("%s: Bad CRC" % (args.file))
  print("Updating to v%u.%u..." % (maj, min))
  send_cmd(struct.pack("<2BI", CMD_UPDATE, 6, len(dat)))
  ser.write(dat)
  (ack,) = struct.unpack("B", ser.read(1))
  if ack != 0:
    print("** UPDATE FAILED: Please retry!")
    return
  print("Done.")
  print("** Disconnect Greaseweazle and remove the Programming Jumper.")

def _main(argv):

  actions = {
    "read" : read,
    "write" : write,
    "update" : update
  }
  
  parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("action")
  parser.add_argument("--revs", type=int, default=3,
                      help="number of revolutions to read per track")
  parser.add_argument("--scyl", type=int, default=0,
                      help="first cylinder to read/write")
  parser.add_argument("--ecyl", type=int, default=81,
                      help="last cylinder to read/write")
  parser.add_argument("--single-sided", action="store_true")
#  parser.add_argument("--total", type=float, default=8.0,
#                      help="total length, seconds")
  parser.add_argument("file", help="in/out filename")
  parser.add_argument("device", help="serial device")
  args = parser.parse_args(argv[1:])

  if not args.action in actions:
    print("** Action \"%s\" is not recognised" % args.action)
    print("Valid actions: ", end="")
    print(", ".join(str(key) for key in actions.keys()))
    return
  
  global ser
  ser = serial.Serial(args.device)
  ser.baudrate = BAUD_CLEAR_COMMS
  ser.baudrate = BAUD_NORMAL
  ser.reset_input_buffer()

  global sample_freq
  info = get_fw_info()
  sample_freq = info[4]
  update_mode = (info[2] == 0)

  print("** %s v%u.%u, Host Tools v%u.%u"
        % (("Greaseweazle","Bootloader")[update_mode], info[0], info[1],
           version.major, version.minor))
  
  if (not update_mode
      and (version.major > info[0]
           or (version.major == info[0] and version.minor > info[1]))):
    print("Firmware is out of date: Require >= v%u.%u"
          % (version.major, version.minor))
    print("Install the Update Jumper and \"update <update_file>\"")
    return
  
  if update_mode and args.action != "update":
    print("Greaseweazle is in Firmware Update Mode:")
    print(" The only available action is \"update <update_file>\"")
    if info[4] & 1:
      print(" Remove the Update Jumper for normal operation")
    else:
      print(" Main firmware is erased: You *must* perform an update!")
    return

  if not update_mode and args.action == "update":
    print("Greaseweazle is in Normal Mode:")
    print(" To \"update\" you must install the Update Jumper")
    return
  
  #set_delays(step_delay=3)
  #print_delays(get_delays())

  actions[args.action](args)

  if not update_mode:
    motor(False)

def main(argv):
  try:
    _main(argv)
  except CmdError as error:
    print("Command Failed: %s" % error)
    
if __name__ == "__main__":
  main(sys.argv)
