#amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth.back.pysim import *

from .utils.wishbone import *
from ..periph.timer import TimerPeripheral


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd"):
        sim.run()


reload_addr     = 0x00 >> 2
en_addr         = 0x04 >> 2
ctr_addr        = 0x08 >> 2
ev_status_addr  = 0x10 >> 2
ev_pending_addr = 0x14 >> 2
ev_enable_addr  = 0x18 >> 2


class TimerPeripheralTestCase(unittest.TestCase):
    def test_invalid_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Counter width must be a non-negative integer, not 'foo'"):
            dut = TimerPeripheral(width="foo")

    def test_invalid_width_32(self):
        with self.assertRaisesRegex(ValueError,
                r"Counter width cannot be greater than 32 \(was: 33\)"):
            dut = TimerPeripheral(width=33)

    def test_simple(self):
        dut = TimerPeripheral(width=4)
        def process():
            yield from wb_write(dut.bus, addr=ctr_addr, data=15, sel=0xf)
            yield
            ctr = yield from wb_read(dut.bus, addr=ctr_addr, sel=0xf)
            self.assertEqual(ctr, 15)
            yield
            yield from wb_write(dut.bus, addr=en_addr,  data=1,  sel=0xf)
            yield
            for i in range(16):
                yield
            ctr = yield from wb_read(dut.bus, addr=ctr_addr, sel=0xf)
            self.assertEqual(ctr, 0)
        simulation_test(dut, process)

    def test_irq(self):
        dut = TimerPeripheral(width=4)
        def process():
            yield from wb_write(dut.bus, addr=ctr_addr, data=15, sel=0xf)
            yield
            yield from wb_write(dut.bus, addr=ev_enable_addr, data=1, sel=0xf)
            yield
            yield from wb_write(dut.bus, addr=en_addr,  data=1,  sel=0xf)
            yield
            done = False
            for i in range(16):
                if (yield dut.irq):
                    self.assertFalse(done)
                    done = True
                    ctr = yield from wb_read(dut.bus, addr=ctr_addr, sel=0xf)
                    self.assertEqual(ctr, 0)
                yield
            self.assertTrue(done)
        simulation_test(dut, process)

    def test_reload(self):
        dut = TimerPeripheral(width=4)
        def process():
            yield from wb_write(dut.bus, addr=reload_addr, data=15, sel=0xf)
            yield
            yield from wb_write(dut.bus, addr=ctr_addr, data=15, sel=0xf)
            yield
            yield from wb_write(dut.bus, addr=ev_enable_addr, data=1, sel=0xf)
            yield
            yield from wb_write(dut.bus, addr=en_addr,  data=1,  sel=0xf)
            yield
            irqs = 0
            for i in range(32):
                if (yield dut.irq):
                    irqs += 1
                    yield from wb_write(dut.bus, addr=ev_pending_addr, data=1, sel=0xf)
                yield
            # not an accurate measure, since each call to wb_write() adds a few cycles,
            # but we can at least check that reloading the timer works.
            self.assertEqual(irqs, 2)
        simulation_test(dut, process)
