# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.back.pysim import *

from amaranth_soc.memory import MemoryMap

from .utils.wishbone import *
from ..periph.base import Peripheral, CSRBank, PeripheralBridge


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd"):
        sim.run()


class PeripheralTestCase(unittest.TestCase):
    def test_name(self):
        class Wrapper(Peripheral):
            def __init__(self):
                super().__init__()
        periph_0 = Wrapper()
        periph_1 = Peripheral(name="periph_1")
        self.assertEqual(periph_0.name, "periph_0")
        self.assertEqual(periph_1.name, "periph_1")

    def test_periph_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            periph = Peripheral(name=2)

    def test_set_bus_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"Bus interface must be an instance of wishbone.Interface, not 'foo'"):
            periph.bus = "foo"

    def test_get_bus_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral <.*> does not have a bus interface"):
            periph.bus

    def test_set_irq_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(TypeError,
                r"IRQ line must be an instance of IRQLine, not 'foo'"):
            periph.irq = "foo"

    def test_get_irq_wrong(self):
        periph = Peripheral(src_loc_at=0)
        with self.assertRaisesRegex(NotImplementedError,
                r"Peripheral <.*> does not have an IRQ line"):
            periph.irq

    def test_iter_csr_banks(self):
        periph = Peripheral(src_loc_at=0)
        bank_0 = periph.csr_bank()
        bank_1 = periph.csr_bank(addr=0x4, alignment=2)
        self.assertEqual(list(periph.iter_csr_banks()), [
            (bank_0, None, None),
            (bank_1,  0x4, 2),
        ])

    def test_iter_windows(self):
        periph = Peripheral(src_loc_at=0)
        win_0 = periph.window(addr_width=2, data_width=8)
        win_1 = periph.window(addr_width=4, data_width=8, addr=0x4, sparse=True)
        self.assertEqual(list(periph.iter_windows()), [
            (win_0, None, None),
            (win_1, 0x4,  True),
        ])

    def test_iter_events(self):
        periph = Peripheral(src_loc_at=0)
        ev_0 = periph.event()
        ev_1 = periph.event(mode="rise")
        self.assertEqual((ev_0.name, ev_0.mode), ("ev_0", "level"))
        self.assertEqual((ev_1.name, ev_1.mode), ("ev_1", "rise"))
        self.assertEqual(list(periph.iter_events()), [
            ev_0,
            ev_1,
        ])


class CSRBankTestCase(unittest.TestCase):
    def test_bank_name(self):
        bank = CSRBank(name="foo")
        self.assertEqual(bank.name, "foo")

    def test_bank_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            bank = CSRBank(name=2)

    def test_csr_name_wrong(self):
        bank = CSRBank()
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            bank.csr(1, "r", name=2)

    def test_iter_csr_regs(self):
        bank = CSRBank()
        csr_0 = bank.csr(1, "r")
        csr_1 = bank.csr(8, "rw", addr=0x4, alignment=2)
        self.assertEqual(list(bank.iter_csr_regs()), [
            (csr_0, None, None),
            (csr_1,  0x4,    2),
        ])


class PeripheralBridgeTestCase(unittest.TestCase):
    def test_periph_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Peripheral must be an instance of Peripheral, not 'foo'"):
            PeripheralBridge('foo', data_width=8, granularity=8, features=(), alignment=0)


class PeripheralSimulationTestCase(unittest.TestCase):
    def test_csrs(self):
        class DummyPeripheral(Peripheral, Elaboratable):
            def __init__(self):
                super().__init__()
                bank         = self.csr_bank(addr=0x100)
                self._csr_0  = bank.csr(8, "r")
                self._csr_1  = bank.csr(8, "r", addr=0x8, alignment=4)
                self._csr_2  = bank.csr(8, "rw")

                self.win_0   = self.window(addr_width=1, data_width=8, sparse=True, addr=0x000)
                self.win_1   = self.window(addr_width=1, data_width=32, granularity=8, addr=0x200)
                self.win_0.memory_map = MemoryMap(addr_width=1, data_width=8)
                self.win_1.memory_map = MemoryMap(addr_width=3, data_width=8)

                self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
                self.bus     = self._bridge.bus

            def elaborate(self, platform):
                m = Module()
                m.submodules.bridge = self._bridge
                m.d.comb += [
                    self._csr_0.r_data.eq(0xa),
                    self._csr_1.r_data.eq(0xb),
                ]
                with m.If(self._csr_2.w_stb):
                    m.d.sync += self._csr_2.r_data.eq(self._csr_2.w_data)
                return m

        dut = DummyPeripheral()

        def process():
            self.assertEqual((yield from wb_read(dut.bus, addr=0x100 >> 2, sel=0xf)), 0xa)
            yield
            self.assertEqual((yield from wb_read(dut.bus, addr=0x108 >> 2, sel=0xf)), 0xb)
            yield
            yield from wb_write(dut.bus, addr=0x118 >> 2, data=0xc, sel=0xf)
            yield
            self.assertEqual((yield from wb_read(dut.bus, addr=0x118 >> 2, sel=0xf)), 0xc)
            yield

            yield dut.bus.cyc.eq(1)
            yield dut.bus.adr.eq(0x000 >> 2)
            yield Delay(1e-7)
            self.assertEqual((yield dut.win_0.cyc), 1)

            yield dut.bus.adr.eq(0x200 >> 2)
            yield Delay(1e-7)
            self.assertEqual((yield dut.win_1.cyc), 1)

        simulation_test(dut, process)

    def test_events(self):
        class DummyPeripheral(Peripheral, Elaboratable):
            def __init__(self):
                super().__init__()
                self.ev_0    = self.event()
                self.ev_1    = self.event(mode="rise")
                self.ev_2    = self.event(mode="fall")
                self._bridge = self.bridge(data_width=8)
                self.bus     = self._bridge.bus
                self.irq     = self._bridge.irq

            def elaborate(self, platform):
                m = Module()
                m.submodules.bridge = self._bridge
                return m

        dut = DummyPeripheral()

        ev_status_addr  = 0x0
        ev_pending_addr = 0x1
        ev_enable_addr  = 0x2

        def process():
            yield dut.ev_0.stb.eq(1)
            yield dut.ev_1.stb.eq(0)
            yield dut.ev_2.stb.eq(1)
            yield
            self.assertEqual((yield dut.irq), 0)
            self.assertEqual((yield from wb_read(dut.bus, ev_status_addr, sel=0xf)), 0b101)
            yield

            yield from wb_write(dut.bus, ev_enable_addr, data=0b111, sel=0xf)
            yield
            self.assertEqual((yield dut.irq), 1)

            yield from wb_write(dut.bus, ev_pending_addr, data=0b001, sel=0xf)
            yield
            self.assertEqual((yield from wb_read(dut.bus, ev_pending_addr, sel=0xf)), 0b001)
            yield
            self.assertEqual((yield dut.irq), 1)
            yield dut.ev_0.stb.eq(0)
            yield from wb_write(dut.bus, ev_pending_addr, data=0b001, sel=0xf)
            yield
            self.assertEqual((yield dut.irq), 0)

            yield dut.ev_1.stb.eq(1)
            yield
            self.assertEqual((yield from wb_read(dut.bus, ev_pending_addr, sel=0xf)), 0b010)
            yield
            self.assertEqual((yield dut.irq), 1)
            yield from wb_write(dut.bus, ev_pending_addr, data=0b010, sel=0xf)
            yield
            self.assertEqual((yield dut.irq), 0)

            yield dut.ev_2.stb.eq(0)
            yield
            self.assertEqual((yield from wb_read(dut.bus, ev_pending_addr, sel=0xf)), 0b100)
            yield
            self.assertEqual((yield dut.irq), 1)
            yield from wb_write(dut.bus, ev_pending_addr, data=0b100, sel=0xf)
            yield
            self.assertEqual((yield dut.irq), 0)

        simulation_test(dut, process)
