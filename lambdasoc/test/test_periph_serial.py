import unittest

from amaranth import *
from amaranth.lib.io import pin_layout
from amaranth.back.pysim import *

from amaranth_stdio.serial import AsyncSerial

from .utils.wishbone import *
from ..periph.serial import AsyncSerialPeripheral


divisor_addr    = 0x00 >> 2
rx_data_addr    = 0x04 >> 2
rx_rdy_addr     = 0x08 >> 2
rx_err_addr     = 0x0c >> 2
tx_data_addr    = 0x10 >> 2
tx_rdy_addr     = 0x14 >> 2
ev_status_addr  = 0x20 >> 2
ev_pending_addr = 0x24 >> 2
ev_enable_addr  = 0x28 >> 2


class AsyncSerialPeripheralTestCase(unittest.TestCase):
    def test_loopback(self):
        pins = Record([("rx", pin_layout(1, dir="i")),
                       ("tx", pin_layout(1, dir="o"))])

        core = AsyncSerial(divisor=5, pins=pins)
        dut = AsyncSerialPeripheral(core=core)
        m = Module()
        m.submodules.serial = dut
        m.d.comb += pins.rx.i.eq(pins.tx.o)

        def process():
            # enable rx_rdy event
            yield from wb_write(dut.bus, addr=ev_enable_addr, data=0b001, sel=0xf)
            yield

            tx_rdy = yield from wb_read(dut.bus, addr=tx_rdy_addr, sel=0xf)
            self.assertEqual(tx_rdy, 1)
            yield

            yield from wb_write(dut.bus, addr=tx_data_addr, data=0xab, sel=0xf)
            yield

            for i in range(61):
                yield
            self.assertTrue((yield dut.irq))

            rx_rdy = yield from wb_read(dut.bus, addr=rx_rdy_addr, sel=0xf)
            self.assertEqual(rx_rdy, 1)
            yield
            rx_data = yield from wb_read(dut.bus, addr=rx_data_addr, sel=0xf)
            self.assertEqual(rx_data, 0xab)
            yield

        sim = Simulator(m)
        sim.add_clock(1e-6)
        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()
