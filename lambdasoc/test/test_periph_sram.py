#amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth.utils import log2_int
from amaranth.back.pysim import *

from amaranth_soc.wishbone import CycleType, BurstTypeExt

from .utils.wishbone import *
from ..periph.sram import SRAMPeripheral


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd"):
        sim.run()


def _burst_type(wrap):
    if wrap == 0:
        return BurstTypeExt.LINEAR
    if wrap == 4:
        return BurstTypeExt.WRAP_4
    if wrap == 8:
        return BurstTypeExt.WRAP_8
    if wrap == 16:
        return BurstTypeExt.WRAP_16
    assert False


class SRAMPeripheralTestCase(unittest.TestCase):
    def read_incr(self, dut, *, addr, count, wrap=0): # FIXME clean
        data = []
        yield dut.bus.cyc.eq(1)
        yield dut.bus.stb.eq(1)
        yield dut.bus.adr.eq(addr)
        yield dut.bus.bte.eq(_burst_type(wrap))
        yield dut.bus.cti.eq(CycleType.END_OF_BURST if count == 0 else CycleType.INCR_BURST)
        yield
        self.assertFalse((yield dut.bus.ack))
        for i in range(count):
            yield
            self.assertTrue((yield dut.bus.ack))
            data.append((yield dut.bus.dat_r))
            if wrap == 0:
                yield dut.bus.adr.eq((yield dut.bus.adr) + 1)
            else:
                yield dut.bus.adr[:log2_int(wrap)].eq((yield dut.bus.adr[:log2_int(wrap)]) + 1)
            yield dut.bus.cti.eq(CycleType.END_OF_BURST if i == count-1 else CycleType.INCR_BURST)
        yield dut.bus.cyc.eq(0)
        yield dut.bus.stb.eq(0)
        return data

    def test_bus(self):
        dut = SRAMPeripheral(size=16, data_width=32, granularity=8)
        self.assertEqual(dut.bus.addr_width,  2)
        self.assertEqual(dut.bus.data_width, 32)
        self.assertEqual(dut.bus.granularity, 8)

    def test_invalid_size(self):
        with self.assertRaisesRegex(ValueError,
                r"Size must be an integer power of two, not 'foo'"):
            dut = SRAMPeripheral(size='foo')
        with self.assertRaisesRegex(ValueError,
                r"Size must be an integer power of two, not 3"):
            dut = SRAMPeripheral(size=3)

    def test_invalid_size_ratio(self):
        with self.assertRaisesRegex(ValueError,
                r"Size 2 cannot be lesser than the data width/granularity ratio of "
                r"4 \(32 / 8\)"):
            dut = SRAMPeripheral(size=2, data_width=32, granularity=8)

    def test_read(self):
        dut = SRAMPeripheral(size=4, data_width=8, writable=False)
        dut.init = [0x00, 0x01, 0x02, 0x03]
        def process():
            for i in range(4):
                data = (yield from wb_read(dut.bus, addr=i, sel=1))
                self.assertEqual(data, dut.init[i])
                yield
        simulation_test(dut, process)

    def test_read_incr_linear(self):
        dut = SRAMPeripheral(size=8, data_width=8, writable=False)
        dut.init = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]
        def process():
            data = (yield from self.read_incr(dut, addr=0x00, count=6))
            self.assertEqual(data, dut.init[:6])
            yield
            data = (yield from self.read_incr(dut, addr=0x06, count=2))
            self.assertEqual(data, dut.init[6:])
        simulation_test(dut, process)

    def test_read_incr_wrap_4(self):
        dut = SRAMPeripheral(size=8, data_width=8, writable=False)
        dut.init = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]
        def process():
            data = (yield from self.read_incr(dut, addr=0x01, count=8, wrap=4))
            self.assertEqual(data, 2*(dut.init[1:4] + [dut.init[0]]))
        simulation_test(dut, process)

    def test_read_incr_wrap_8(self):
        dut = SRAMPeripheral(size=8, data_width=8, writable=False)
        dut.init = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]
        def process():
            data = (yield from self.read_incr(dut, addr=0x06, count=16, wrap=8))
            self.assertEqual(data, 2*(dut.init[6:] + dut.init[:6]))
        simulation_test(dut, process)

    def test_read_incr_wrap_16(self):
        dut = SRAMPeripheral(size=16, data_width=8, writable=False)
        dut.init = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f]
        def process():
            data = (yield from self.read_incr(dut, addr=0x06, count=32, wrap=16))
            self.assertEqual(data, 2*(dut.init[6:] + dut.init[:6]))
        simulation_test(dut, process)

    def test_write(self):
        dut = SRAMPeripheral(size=4, data_width=8)
        def process():
            data = [0x00, 0x01, 0x02, 0x03]
            for i in range(len(data)):
                yield from wb_write(dut.bus, addr=i, data=data[i], sel=1)
                yield
            for i in range(len(data)):
                b = yield from wb_read(dut.bus, addr=i, sel=1)
                yield
                self.assertEqual(b, data[i])
        simulation_test(dut, process)

    def test_write_sel(self):
        dut = SRAMPeripheral(size=4, data_width=16, granularity=8)
        def process():
            yield from wb_write(dut.bus, addr=0x0, data=0x5aa5, sel=0b01)
            yield
            yield from wb_write(dut.bus, addr=0x1, data=0x5aa5, sel=0b10)
            yield
            self.assertEqual((yield from wb_read(dut.bus, addr=0x0, sel=1)), 0x00a5)
            yield
            self.assertEqual((yield from wb_read(dut.bus, addr=0x1, sel=1)), 0x5a00)
        simulation_test(dut, process)

    # TODO test write bursts
