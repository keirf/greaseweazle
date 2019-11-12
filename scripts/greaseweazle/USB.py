# greaseweazle/USB.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct, collections
from greaseweazle import version

## Control-Path command set
class ControlCmd:
    ClearComms      = 10000
    Normal          =  9600


## Command set
class Cmd:
    GetInfo         =  0
    Seek            =  1
    Side            =  2
    SetParams       =  3
    GetParams       =  4
    Motor           =  5
    ReadFlux        =  6
    WriteFlux       =  7
    GetFluxStatus   =  8
    GetIndexTimes   =  9
    Select          = 10
    # Bootloader specific:
    Update          =  1


## Command responses/acknowledgements
class Ack:
    Okay            = 0
    BadCommand      = 1
    NoIndex         = 2
    NoTrk0          = 3
    FluxOverflow    = 4
    FluxUnderflow   = 5
    Wrprot          = 6
    Max             = 6


## Cmd.{Get,Set}Params indexes
class Params:
    Delays          = 0


## CmdError: Encapsulates a command acknowledgement.
class CmdError(Exception):

    str = [ "Okay", "Bad Command", "No Index", "Track 0 not found",
            "Flux Overflow", "Flux Underflow", "Disk is Write Protected" ]

    def __init__(self, cmd, code):
        self.cmd = cmd
        self.code = code

    def __str__(self):
        if self.code <= Ack.Max:
            return self.str[self.code]
        return "Unknown Error (%u)" % self.code


class Unit:

    ## Unit information, instance variables:
    ##  major, minor: Greaseweazle firmware version number
    ##  max_index:    Maximum index timings for Cmd.ReadFlux
    ##  max_cmd:      Maximum Cmd number accepted by this unit
    ##  sample_freq:  Resolution of all time values passed to/from this unit

    ## Unit(ser):
    ## Accepts a Pyserial instance for Greaseweazle communications.
    def __init__(self, ser):
        self.ser = ser
        self.reset()
        # Copy firmware info to instance variables (see above for definitions).
        self.send_cmd(struct.pack("3B", Cmd.GetInfo, 3, 0))
        x = struct.unpack("<4BI24x", self.ser.read(32))
        (self.major, self.minor, self.max_index,
         self.max_cmd, self.sample_freq) = x
        # Check whether firmware is in update mode: limited command set if so.
        self.update_mode = (self.max_index == 0)
        if self.update_mode:
            self.update_jumpered = (self.sample_freq & 1)
            del self.max_index
            del self.sample_freq
            return
        # We are running main firmware: Check whether an update is needed.
        # We can use only the GetInfo command if the firmware is out of date.
        self.update_needed = (version.major != self.major
                              or version.minor != self.minor)
        if self.update_needed:
            return
        # Initialise the delay properties with current firmware values.
        self.send_cmd(struct.pack("4B", Cmd.GetParams, 4, Params.Delays, 10))
        (self._select_delay, self._step_delay,
         self._seek_settle_delay, self._motor_delay,
         self._auto_off_delay) = struct.unpack("<5H", self.ser.read(10))


    ## reset:
    ## Resets communications with Greaseweazle.
    def reset(self):
        self.ser.reset_output_buffer()
        self.ser.baudrate = ControlCmd.ClearComms
        self.ser.baudrate = ControlCmd.Normal
        self.ser.reset_input_buffer()


    ## send_cmd:
    ## Send given command byte sequence to Greaseweazle.
    ## Raise a CmdError if command fails.
    def send_cmd(self, cmd):
        self.ser.write(cmd)
        (c,r) = struct.unpack("2B", self.ser.read(2))
        assert c == cmd[0]
        if r != 0:
            raise CmdError(c,r)


    ## seek:
    ## Seek the selected drive's heads to the specified track (cyl, side).
    def seek(self, cyl, side):
        self.send_cmd(struct.pack("3B", Cmd.Seek, 3, cyl))
        self.send_cmd(struct.pack("3B", Cmd.Side, 3, side))


    ## drive_select:
    ## Select/deselect the drive.
    def drive_select(self, state):
        self.send_cmd(struct.pack("3B", Cmd.Select, 3, int(state)))


    ## drive_motor:
    ## Turn the selected drive's motor on/off.
    def drive_motor(self, state):
        self.send_cmd(struct.pack("3B", Cmd.Motor, 3, int(state)))


    ## get_index_times:
    ## Get index timing values for the last .read_track() command.
    def get_index_times(self, nr):
        self.send_cmd(struct.pack("4B", Cmd.GetIndexTimes, 4, 0, nr))
        x = struct.unpack("<%dI" % nr, self.ser.read(4*nr))
        return x


    ## update_firmware:
    ## Update Greaseweazle to the given new firmware.
    def update_firmware(self, dat):
        self.send_cmd(struct.pack("<2BI", Cmd.Update, 6, len(dat)))
        self.ser.write(dat)
        (ack,) = struct.unpack("B", self.ser.read(1))
        return ack


    ## decode_flux:
    ## Decode the Greaseweazle data stream into a list of flux samples.
    def decode_flux(self, dat):
        flux = []
        while dat:
            i = dat.popleft()
            if i < 250:
                flux.append(i)
            elif i == 255:
                val =  (dat.popleft() & 254) >>  1
                val += (dat.popleft() & 254) <<  6
                val += (dat.popleft() & 254) << 13
                val += (dat.popleft() & 254) << 20
                flux.append(val)
            else:
                val = (i - 249) * 250
                val += dat.popleft() - 1
                flux.append(val)
        assert flux[-1] == 0
        return flux[:-1]


    ## encode_flux:
    ## Convert the given flux timings into an encoded data stream.
    def encode_flux(self, flux):
        dat = bytearray()
        for val in flux:
            if val == 0:
                pass
            elif val < 250:
                dat.append(val)
            else:
                high = val // 250
                if high <= 5:
                    dat.append(249+high)
                    dat.append(1 + val%250)
                else:
                    dat.append(255)
                    dat.append(1 | (val<<1) & 255)
                    dat.append(1 | (val>>6) & 255)
                    dat.append(1 | (val>>13) & 255)
                    dat.append(1 | (val>>20) & 255)
        dat.append(0) # End of Stream
        return dat


    ## read_track:
    ## Read flux timings as encoded data stream for the current track.
    def read_track(self, nr_idx):
        dat = collections.deque()
        self.send_cmd(struct.pack("3B", Cmd.ReadFlux, 3, nr_idx))
        while True:
            dat += self.ser.read(1)
            dat += self.ser.read(self.ser.in_waiting)
            if dat[-1] == 0:
                break
        try:
            self.send_cmd(struct.pack("2B", Cmd.GetFluxStatus, 2))
        except CmdError as error:
            del dat
            return error.code, None, None
        return Ack.Okay, self.get_index_times(nr_idx), dat


    ## write_track:
    ## Write the given data stream to the current track via Greaseweazle.
    def write_track(self, dat):
        self.send_cmd(struct.pack("<2BIB", Cmd.WriteFlux, 7, 0, 1))
        self.ser.write(dat)
        self.ser.read(1) # Sync with Greaseweazle
        try:
            self.send_cmd(struct.pack("2B", Cmd.GetFluxStatus, 2))
        except CmdError as error:
            return error.code
        return Ack.Okay


    ##
    ## Delay-property public getters and setters:
    ##  select_delay:      Delay (usec) after asserting drive select
    ##  step_delay:        Delay (usec) after issuing a head-step command
    ##  seek_settle_delay: Delay (msec) after completing a head-seek operation
    ##  motor_delay:       Delay (msec) after turning on drive spindle motor
    ##  auto_off_delay:    Timeout (msec) since last command upon which all
    ##                     drives are deselected and spindle motors turned off
    ##

    def _set_delays(self):
        self.send_cmd(struct.pack("<3B5H", Cmd.SetParams,
                                  3+5*2, Params.Delays,
                                  self._select_delay, self._step_delay,
                                  self._seek_settle_delay,
                                  self._motor_delay, self._auto_off_delay))

    @property
    def select_delay(self):
        return self._select_delay
    @select_delay.setter
    def select_delay(self, select_delay):
        self._select_delay = select_delay
        self._set_delays()

    @property
    def step_delay(self):
        return self._step_delay
    @step_delay.setter
    def step_delay(self, step_delay):
        self._step_delay = step_delay
        self._set_delays()

    @property
    def seek_settle_delay(self):
        return self._seek_settle_delay
    @seek_settle_delay.setter
    def seek_settle_delay(self, seek_settle_delay):
        self._seek_settle_delay = seek_settle_delay
        self._set_delays()

    @property
    def motor_delay(self):
        return self._motor_delay
    @motor_delay.setter
    def motor_delay(self, motor_delay):
        self._motor_delay = motor_delay
        self._set_delays()

    @property
    def auto_off_delay(self):
        return self._auto_off_delay
    @auto_off_delay.setter
    def auto_off_delay(self, auto_off_delay):
        self._auto_off_delay = auto_off_delay
        self._set_delays()

# Local variables:
# python-indent: 4
# End:
