# greaseweazle/usb.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Any, List, Tuple, Union

import struct
import itertools as it
from enum import Enum
from greaseweazle import error
from greaseweazle.flux import Flux
from greaseweazle import optimised

EARLIEST_SUPPORTED_FIRMWARE = (0, 31)

## Control-Path command set
class ControlCmd:
    ClearComms      = 10000
    Normal          =  9600


## Command set
class Cmd:
    GetInfo         =  0
    Update          =  1
    Seek            =  2
    Head            =  3
    SetParams       =  4
    GetParams       =  5
    Motor           =  6
    ReadFlux        =  7
    WriteFlux       =  8
    GetFluxStatus   =  9
    GetIndexTimes   = 10
    SwitchFwMode    = 11
    Select          = 12
    Deselect        = 13
    SetBusType      = 14
    SetPin          = 15
    Reset           = 16
    EraseFlux       = 17
    SourceBytes     = 18
    SinkBytes       = 19
    GetPin          = 20
    TestMode        = 21
    NoClickStep     = 22
    str = {
        GetInfo: "GetInfo",
        Update: "Update",
        Seek: "Seek",
        Head: "Head",
        SetParams: "SetParams",
        GetParams: "GetParams",
        Motor: "Motor",
        ReadFlux: "ReadFlux",
        WriteFlux: "WriteFlux",
        GetFluxStatus: "GetFluxStatus",
        GetIndexTimes: "GetIndexTimes",
        SwitchFwMode: "SwitchFwMode",
        Select: "Select",
        Deselect: "Deselect",
        SetBusType: "SetBusType",
        SetPin: "SetPin",
        Reset: "Reset",
        EraseFlux: "EraseFlux",
        SourceBytes: "SourceBytes",
        SinkBytes: "SinkBytes",
        GetPin: "GetPin",
        TestMode: "TestMode",
        NoClickStep: "NoClickStep"
    }


## Command responses/acknowledgements
class Ack:
    Okay            =  0
    BadCommand      =  1
    NoIndex         =  2
    NoTrk0          =  3
    FluxOverflow    =  4
    FluxUnderflow   =  5
    Wrprot          =  6
    NoUnit          =  7
    NoBus           =  8
    BadUnit         =  9
    BadPin          = 10
    BadCylinder     = 11
    OutOfSRAM       = 12
    OutOfFlash      = 13
    str = {
        Okay: "Okay",
        BadCommand: "Bad Command",
        NoIndex: "No Index",
        NoTrk0: "Track 0 not found",
        FluxOverflow: "Flux Overflow",
        FluxUnderflow: "Flux Underflow",
        Wrprot: "Disk is Write Protected",
        NoUnit: "No drive unit selected",
        NoBus: "No bus type (eg. Shugart, IBM/PC) specified",
        BadUnit: "Invalid unit number",
        BadPin: "Invalid pin",
        BadCylinder: "Invalid cylinder",
        OutOfSRAM: "Out of SRAM",
        OutOfFlash: "Out of Flash"
    }



## Cmd.GetInfo indexes
class GetInfo:
    Firmware        = 0
    BandwidthStats  = 1
    CurrentDrive    = 7


## Cmd.{Get,Set}Params indexes
class Params:
    Delays          = 0


## Cmd.SetBusType values
class BusType(Enum):
    Invalid            = 0
    IBMPC              = 1
    Shugart            = 2


## Flux read stream opcodes, preceded by 0xFF byte
class FluxOp:
    Index           = 1
    Space           = 2
    Astable         = 3


## Cmd.GetInfo DriveInfo result
class DriveInfo:

    FLAG_CYL_VALID = 1
    FLAG_MOTOR_ON  = 2
    FLAG_IS_FLIPPY = 4

    def __init__(self, rsp):
        flags, cyl = struct.unpack("<Ii24x", rsp)
        self.cyl = cyl if (flags & self.FLAG_CYL_VALID) != 0 else None
        self.motor_on = (flags & self.FLAG_MOTOR_ON) != 0
        self.is_flippy = (flags & self.FLAG_IS_FLIPPY) != 0

    def __str__(self):
        s = "Cyl: " + ("Unknown" if self.cyl is None else str(self.cyl))
        if self.motor_on:
            s += "; Motor-On"
        if self.is_flippy:
            s += "; Is-Flippy"
        return s


## CmdError: Encapsulates a command acknowledgement.
class CmdError(Exception):

    def __init__(self, cmd, code):
        self.cmd = cmd
        self.code = code

    def cmd_str(self):
        return Cmd.str.get(self.cmd[0], "UnknownCmd")
        
    def errcode_str(self):
        if self.code == Ack.BadCylinder and self.cmd[0] == Cmd.Seek:
            s = Ack.str[Ack.BadCylinder]
            cyl = struct.unpack('2Bb' if len(self.cmd) == 3 else '2Bh',
                                self.cmd)[2]
            return s + f' {cyl}'
        return Ack.str.get(self.code, "Unknown Error (%u)" % self.code)

    def __str__(self):
        return "%s: %s" % (self.cmd_str(), self.errcode_str())


class Unit:

    ## Unit information, instance variables:
    ##  major, minor: Greaseweazle firmware version number
    ##  max_cmd:      Maximum Cmd number accepted by this unit
    ##  sample_freq:  Resolution of all time values passed to/from this unit
    ##  update_mode:  True iff the Greaseweazle unit is in update mode

    ## Unit(ser):
    ## Accepts a Pyserial instance for Greaseweazle communications.
    def __init__(self, ser):
        self.ser = ser
        self.reset()
        # Copy firmware info to instance variables (see above for definitions).
        self._send_cmd(struct.pack("3B", Cmd.GetInfo, 3, GetInfo.Firmware))
        x = struct.unpack("<4BI4B3H14x", self.ser.read(32))
        (self.major, self.minor, is_main_firmware,
         self.max_cmd, self.sample_freq, self.hw_model,
         self.hw_submodel, self.usb_speed,
         self.mcu_id, self.mcu_mhz, self.mcu_sram_kb, self.usb_buf_kb) = x
        self.version = (self.major, self.minor)
        # Old firmware doesn't report HW type but runs on STM32F1 only.
        if self.hw_model == 0:
            self.hw_model = 1
        # Check whether firmware is in update mode: limited command set if so.
        self.update_mode = (is_main_firmware == 0)
        if self.update_mode:
            self.update_jumpered = (self.sample_freq & 1)
            del self.sample_freq
            return
        # We are running main firmware: Check whether an update is needed.
        # We can use only the GetInfo command if the firmware is out of date.
        self.update_needed = (self.version < EARLIEST_SUPPORTED_FIRMWARE)
        if self.update_needed:
            return


    ## reset:
    ## Resets communications with Greaseweazle.
    def reset(self) -> None:
        self.ser.reset_output_buffer()
        self.ser.baudrate = ControlCmd.ClearComms
        self.ser.baudrate = ControlCmd.Normal
        self.ser.reset_input_buffer()
        self.ser.close()
        self.ser.open()


    ## _send_cmd:
    ## Send given command byte sequence to Greaseweazle.
    ## Raise a CmdError if command fails.
    def _send_cmd(self, cmd) -> None:
        self.ser.write(cmd)
        (c,r) = struct.unpack("2B", self.ser.read(2))
        error.check(c == cmd[0], "Command returned garbage (%02x != %02x)"
                    % (c, cmd[0]))
        if r != 0:
            raise CmdError(cmd, r)


    def get_current_drive_info(self) -> DriveInfo:
        self._send_cmd(struct.pack("3B", Cmd.GetInfo, 3, GetInfo.CurrentDrive))
        return DriveInfo(self.ser.read(32))


    def get_params(self, idx: int, nr: int) -> bytes:
        self._send_cmd(struct.pack("4B", Cmd.GetParams, 4, idx, nr))
        return self.ser.read(nr)


    def set_params(self, idx: int, dat: bytes) -> None:
        self._send_cmd(struct.pack(f'<3B{len(dat)}s', Cmd.SetParams,
                                   3+len(dat), idx, dat))


    ## seek:
    ## Seek the selected drive's heads to the specified track (cyl, head).
    def seek(self, cyl, head) -> None:
        if -0x80 <= cyl <= 0x7f:
            cmd = struct.pack("2Bb", Cmd.Seek, 3, cyl)
        elif -0x8000 <= cyl <= 0x7fff:
            cmd = struct.pack("2Bh", Cmd.Seek, 4, cyl)
        else:
            raise error.Fatal(f'Seek: Invalid cylinder {cyl}')
        self._send_cmd(cmd)
        trk0 = not self.get_pin(26)
        if cyl == 0 and not trk0:
            # This can happen with Kryoflux flippy-modded Panasonic drives
            # which may not assert the /TRK0 signal when stepping *inward*
            # from cylinder -1. We can check this by attempting a fake outward
            # step, which is exactly NoClickStep's purpose.
            try:
                info = self.get_current_drive_info()
                if info.is_flippy:
                    self._send_cmd(struct.pack("2B", Cmd.NoClickStep, 2))
            except CmdError:
                # GetInfo.CurrentDrive is unsupported by older firmwares.
                # NoClickStep is "best effort". We're on a likely error
                # path anyway, so let them fail silently.
                pass
            trk0 = not self.get_pin(26) # now re-sample /TRK0
        error.check(cyl < 0 or (cyl == 0) == trk0,
                    '''\
Track0 signal %s after seek to cylinder %d
 1. Try "gw reset" to re-calibrate the drive-head position
 2. If the error persists try slowing down seek operations
     eg. "gw delays --step 20000" for 20ms per step'''
                    % (('absent', 'asserted')[trk0], cyl))
        self._send_cmd(struct.pack("3B", Cmd.Head, 3, head))


    ## set_bus_type:
    ## Set the floppy bus type.
    def set_bus_type(self, type) -> None:
        self._send_cmd(struct.pack("3B", Cmd.SetBusType, 3, type))


    ## set_pin:
    ## Set a pin level.
    def set_pin(self, pin, level) -> None:
        self._send_cmd(struct.pack("4B", Cmd.SetPin, 4, pin, int(level)))


    ## get_pin:
    ## Get a pin level.
    def get_pin(self, pin) -> bool:
        self._send_cmd(struct.pack("3B", Cmd.GetPin, 3, pin))
        v, = struct.unpack("B", self.ser.read(1))
        return bool(v)


    ## power_on_reset:
    ## Re-initialise to power-on defaults.
    def power_on_reset(self) -> None:
        self._send_cmd(struct.pack("2B", Cmd.Reset, 2))


    ## drive_select:
    ## Select the specified drive unit.
    def drive_select(self, unit) -> None:
        self._send_cmd(struct.pack("3B", Cmd.Select, 3, unit))


    ## drive_deselect:
    ## Deselect currently-selected drive unit (if any).
    def drive_deselect(self) -> None:
        self._send_cmd(struct.pack("2B", Cmd.Deselect, 2))


    ## drive_motor:
    ## Turn the specified drive's motor on/off.
    def drive_motor(self, unit, state) -> None:
        self._send_cmd(struct.pack("4B", Cmd.Motor, 4, unit, int(state)))


    ## switch_fw_mode:
    ## Switch between bootloader and main firmware.
    def switch_fw_mode(self, mode) -> None:
        self._send_cmd(struct.pack("3B", Cmd.SwitchFwMode, 3, int(mode)))


    ## update_main_firmware:
    ## Update Greaseweazle with the given new main firmware.
    def update_main_firmware(self, dat):
        self._send_cmd(struct.pack("<2BI", Cmd.Update, 6, len(dat)))
        self.ser.write(dat)
        (ack,) = struct.unpack("B", self.ser.read(1))
        return ack


    ## update_bootloader:
    ## Update Greaseweazle with the given new bootloader.
    def update_bootloader(self, dat) -> int:
        self._send_cmd(struct.pack("<2B2I", Cmd.Update, 10,
                                   len(dat), 0xdeafbee3))
        self.ser.write(dat)
        (ack,) = struct.unpack("B", self.ser.read(1))
        return ack


    ## _decode_flux:
    ## Decode the Greaseweazle data stream into a list of flux samples.
    def _decode_flux(self, dat: bytes) -> Tuple[List[float], List[float]]:
        flux: List[float] = []
        index: List[float] = []
        assert dat[-1] == 0
        dat_i = it.islice(dat, 0, len(dat)-1)
        ticks, ticks_since_index = 0, 0
        def _read_28bit():
            val =  (next(dat_i) & 254) >>  1
            val += (next(dat_i) & 254) <<  6
            val += (next(dat_i) & 254) << 13
            val += (next(dat_i) & 254) << 20
            return val
        try:
            while True:
                i = next(dat_i)
                if i == 255:
                    opcode = next(dat_i)
                    if opcode == FluxOp.Index:
                        val = _read_28bit()
                        index.append(ticks_since_index + ticks + val)
                        ticks_since_index = -(ticks + val)
                    elif opcode == FluxOp.Space:
                        ticks += _read_28bit()
                    else:
                        raise error.Fatal("Bad opcode in flux stream (%d)"
                                          % opcode)
                else:
                    if i < 250:
                        val = i
                    else:
                        val = 250 + (i - 250) * 255
                        val += next(dat_i) - 1
                    ticks += val
                    flux.append(ticks)
                    ticks_since_index += ticks
                    ticks = 0
        except StopIteration:
            pass
        return flux, index


    ## _encode_flux:
    ## Convert the given flux timings into an encoded data stream.
    def _encode_flux(self, flux: List[int]) -> bytes:
        nfa_thresh = round(150e-6 * self.sample_freq)  # 150us
        nfa_period = round(1.25e-6 * self.sample_freq) # 1.25us
        dat = bytearray()
        def _write_28bit(x):
            dat.append(1 | (x<<1) & 255)
            dat.append(1 | (x>>6) & 255)
            dat.append(1 | (x>>13) & 255)
            dat.append(1 | (x>>20) & 255)
        # Emit a dummy final flux value. This is never written to disk because
        # the write is aborted immediately the final flux is loaded into the
        # WDATA timer. The dummy flux is sacrificial, ensuring that the real
        # final flux gets written in full.
        dummy_flux = round(100e-6 * self.sample_freq)
        for val in it.chain(flux, [dummy_flux]):
            if val == 0:
                pass
            elif val < 250:
                dat.append(val)
            elif val > nfa_thresh:
                dat.append(255)
                dat.append(FluxOp.Space)
                _write_28bit(val)
                dat.append(255)
                dat.append(FluxOp.Astable)
                _write_28bit(nfa_period)
            else:
                high = (val-250) // 255
                if high < 5:
                    dat.append(250 + high)
                    dat.append(1 + (val-250) % 255)
                else:
                    dat.append(255)
                    dat.append(FluxOp.Space)
                    _write_28bit(val - 249)
                    dat.append(249)
        dat.append(0) # End of Stream
        return dat


    ## _read_track:
    ## Private helper which issues command requests to Greaseweazle.
    def _read_track(self, revs, ticks) -> bytes:

        # Request and read all flux timings for this track.
        dat = bytearray()
        self._send_cmd(struct.pack("<2BIH", Cmd.ReadFlux, 8,
                                   ticks, 0 if revs==0 else revs+1))
        while True:
            dat += self.ser.read(1)
            dat += self.ser.read(self.ser.in_waiting)
            if dat[-1] == 0:
                break

        # Check flux status. An exception is raised if there was an error.
        self._send_cmd(struct.pack("2B", Cmd.GetFluxStatus, 2))

        return dat


    ## read_track:
    ## Read and decode flux and index timings for the current track.
    def read_track(self, revs:int, ticks:int=0, nr_retries:int=5) -> Flux:

        retry = 0
        while True:
            try:
                dat = self._read_track(revs, ticks)
            except CmdError as error:
                # An error occurred. We may retry on transient overflows.
                if error.code == Ack.FluxOverflow and retry < nr_retries:
                    retry += 1
                else:
                    raise error
            else:
                # Success!
                break

        try:
            # Decode the flux list and read the index-times list.
            flux_list, index_list = optimised.decode_flux(dat)
        except AttributeError:
            flux_list, index_list = self._decode_flux(dat)

        # Success: Return the requested full index-to-index revolutions.
        return Flux(index_list, flux_list, self.sample_freq, index_cued=False)


    ## write_track:
    ## Write the given flux stream to the current track via Greaseweazle.
    def write_track(self, flux_list, terminate_at_index,
                    cue_at_index=True, nr_retries=5,
                    hard_sector_ticks=0) -> None:

        # Create encoded data stream.
        dat = self._encode_flux(flux_list)
        
        retry = 0
        while True:
            try:
                # Write the flux stream to the track via Greaseweazle.
                if hard_sector_ticks != 0:
                    self._send_cmd(struct.pack("4BI", Cmd.WriteFlux, 8,
                                               int(cue_at_index),
                                               int(terminate_at_index),
                                               hard_sector_ticks))
                else:
                    self._send_cmd(struct.pack("4B", Cmd.WriteFlux, 4,
                                               int(cue_at_index),
                                               int(terminate_at_index)))
                self.ser.write(dat)
                self.ser.read(1) # Sync with Greaseweazle
                self._send_cmd(struct.pack("2B", Cmd.GetFluxStatus, 2))
            except CmdError as error:
                # An error occurred. We may retry on transient underflows.
                if error.code == Ack.FluxUnderflow and retry < nr_retries:
                    retry += 1
                else:
                    raise error
            else:
                # Success!
                break


    ## erase_track:
    ## Erase the current track via Greaseweazle.
    def erase_track(self, ticks) -> None:
        self._send_cmd(struct.pack("<2BI", Cmd.EraseFlux, 6, int(ticks)))
        self.ser.read(1) # Sync with Greaseweazle
        self._send_cmd(struct.pack("2B", Cmd.GetFluxStatus, 2))


    ## source_bytes:
    ## Command Greaseweazle to source 'nr' garbage bytes.
    def source_bytes(self, nr, seed) -> bytes:
        self._send_cmd(struct.pack("<2B2I", Cmd.SourceBytes, 10, nr, seed))
        return self.ser.read(nr)

    ## sink_bytes:
    ## Command Greaseweazle to sink given data buffer.
    def sink_bytes(self, dat, seed) -> int:
        self._send_cmd(struct.pack("<2BII", Cmd.SinkBytes, 10, len(dat), seed))
        self.ser.write(dat)
        (ack,) = struct.unpack("B", self.ser.read(1))
        return ack


    ## bw_stats:
    ## Get min/max bandwidth for previous source/sink command. Mbps (float).
    def bw_stats(self) -> Tuple[float, float]:
        self._send_cmd(struct.pack("3B", Cmd.GetInfo, 3,
                                   GetInfo.BandwidthStats))
        min_bytes, min_usecs, max_bytes, max_usecs = struct.unpack(
            "<4I16x", self.ser.read(32))
        min_bw = (8 * min_bytes) / min_usecs
        max_bw = (8 * max_bytes) / max_usecs
        return min_bw, max_bw


# Local variables:
# python-indent: 4
# End:
