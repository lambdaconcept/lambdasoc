# amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth.test.utils import *
from amaranth.asserts import *
from amaranth.utils import log2_int

from amaranth_soc import wishbone

from ..periph.sdram import *
from ..cores import litedram

from .utils.wishbone import WishboneSubordinateSpec
from .utils.formal import FormalTestCase


class WritebackCacheSpec(Elaboratable):
    def __init__(self, dut):
        self.dut = dut

    def elaborate(self, platform):
        m = Module()

        m.submodules.dut = dut = self.dut

        # Wishbone interface

        m.submodules.wb_sub_spec = WishboneSubordinateSpec(self.dut.intr_bus)

        ratio        = dut.dram_port.data_width // dut.intr_bus.data_width
        nb_lines     = (dut.size * dut.intr_bus.granularity) // dut.dram_port.data_width
        intr_bus_adr = Record([
            ("offset", log2_int(ratio)),
            ("line",   log2_int(nb_lines)),
            ("tag",    dut.intr_bus.addr_width - log2_int(nb_lines) - log2_int(ratio)),
        ])
        m.d.comb += [
            Assert(len(intr_bus_adr) == len(dut.intr_bus.adr)),
            intr_bus_adr.eq(dut.intr_bus.adr),
        ]

        dram_spec_addr = AnyConst(dut.dram_port.addr_width)
        dram_spec_data = Signal(dut.dram_port.data_width)
        dram_spec_line = Array(
            Signal(dut.intr_bus.data_width, name=f"dram_spec_word_{i}")
            for i in range(ratio)
        )

        m.d.comb += dram_spec_data.eq(Cat(dram_spec_line))

        with m.If(Initial()):
            m.d.comb += Assume(dram_spec_data == 0)

        intr_dram_addr = Signal.like(dram_spec_addr)
        m.d.comb += intr_dram_addr.eq(Cat(intr_bus_adr.line, intr_bus_adr.tag))

        with m.If(dut.intr_bus.cyc & dut.intr_bus.stb & dut.intr_bus.ack
                & (intr_dram_addr == dram_spec_addr)
                & dut.intr_bus.we):
            dram_spec_word = dram_spec_line[intr_bus_adr.offset]
            for i, sel_bit in enumerate(dut.intr_bus.sel):
                dram_spec_bits = dram_spec_word    .word_select(i, dut.intr_bus.granularity)
                intr_data_bits = dut.intr_bus.dat_w.word_select(i, dut.intr_bus.granularity)
                with m.If(sel_bit):
                    m.d.sync += dram_spec_bits.eq(intr_data_bits)

        # * A cache hit at `dram_spec_addr` must be coherent with `dram_spec_data`.

        with m.If(dut.intr_bus.cyc & dut.intr_bus.stb & dut.intr_bus.ack
                & (intr_dram_addr == dram_spec_addr)):
            dram_spec_word = dram_spec_line[intr_bus_adr.offset]
            m.d.comb += Assert(dut.intr_bus.dat_r == dram_spec_word)

        # DRAM interface

        dram_cmd  = Record([
            ("addr", dut.dram_port.addr_width),
            ("we",   1),
        ])
        dram_data = Record([
            ("r", dut.dram_port.data_width),
            ("w", dut.dram_port.data_width),
        ])
        dram_done = Record([
            ("cmd", 1),
            ("r",   1),
            ("w",   1),
        ])

        with m.If(Initial()):
            m.d.comb += Assume(~dram_done.any())

        with m.If(dut.dram_port.cmd.valid & dut.dram_port.cmd.ready):
            m.d.sync += [
                dram_done.cmd.eq(1),
                dram_cmd.addr.eq(dut.dram_port.cmd.addr),
                dram_cmd.we  .eq(dut.dram_port.cmd.we),
            ]
        with m.If(dut.dram_port.w.valid & dut.dram_port.w.ready):
            m.d.sync += [
                dram_done.w.eq(1),
                dram_data.w.eq(dut.dram_port.w.data),
            ]
        with m.If(dut.dram_port.r.ready & dut.dram_port.r.valid):
            m.d.sync += [
                dram_done.r.eq(1),
                dram_data.r.eq(dut.dram_port.r.data),
            ]

        with m.If(dram_done.cmd & dram_done.r):
            with m.If(dram_cmd.addr == dram_spec_addr):
                m.d.comb += Assume(dram_data.r == dram_spec_data)

        # Some of the following constraints are tighter than what the LiteDRAM native interface
        # actually allows. We may relax them in the future to improve cache performance.

        # * A new command must not be initiated before the previous one has completed.

        with m.If(dut.dram_port.cmd.valid):
            m.d.comb += Assert(~dram_done.cmd)
        with m.If(dut.dram_port.w.valid):
            m.d.comb += Assert(~dram_done.w)
        with m.If(dut.dram_port.r.ready):
            m.d.comb += Assert(~dram_done.r)

        # * A command may either be a read or a write, but not both.

        with m.If(dram_done.cmd):
            with m.If(dram_cmd.we):
                m.d.comb += Assert(~dram_done.r)
            with m.Else():
                m.d.comb += Assert(~dram_done.w)

        m.d.comb += [
            Assert(dram_done.r.implies(~dram_done.w)),
            Assert(dram_done.w.implies(~dram_done.r)),
        ]

        # * A read command consists of:
        #   - a transaction on the `dram.cmd` stream with `dram.cmd.we` de-asserted;
        #   - a transaction on the `dram.r` stream.

        with m.If(dram_done.cmd & dram_done.r):
            m.d.comb += Assert(~dram_cmd.we)
            m.d.sync += [
                dram_done.cmd.eq(0),
                dram_done.r  .eq(0),
            ]

        # * A write command consists of:
        #   - a transaction on the `dram.cmd` stream with `dram.cmd.we` asserted;
        #   - a transaction on the `dram.w` stream.

        with m.If(dram_done.cmd & dram_done.w):
            m.d.comb += Assert(dram_cmd.we)
            m.d.sync += [
                dram_done.cmd.eq(0),
                dram_done.w  .eq(0),
            ]

        # * A DRAM write at `dram_spec_addr` must be coherent with `dram_spec_data`.

        with m.If(dram_done.cmd & dram_done.w):
            with m.If(dram_cmd.addr == dram_spec_addr):
                m.d.comb += Assert(dram_data.w == dram_spec_data)

        # For fairness, assume that any stream transaction completes in at most 3 clock cycles.

        dram_wait = Record([
            ("cmd", range(2)),
            ("r",   range(2)),
            ("w",   range(2)),
        ])

        with m.If(dut.dram_port.cmd.valid & ~dut.dram_port.cmd.ready):
            m.d.sync += dram_wait.cmd.eq(dram_wait.cmd + 1)
        with m.Else():
            m.d.sync += dram_wait.cmd.eq(0)

        with m.If(dut.dram_port.w.valid & ~dut.dram_port.w.ready):
            m.d.sync += dram_wait.w.eq(dram_wait.w + 1)
        with m.Else():
            m.d.sync += dram_wait.w.eq(0)

        with m.If(dut.dram_port.r.ready & ~dut.dram_port.r.valid):
            m.d.sync += dram_wait.r.eq(dram_wait.r + 1)
        with m.Else():
            m.d.sync += dram_wait.r.eq(0)

        m.d.comb += [
            Assume(dram_wait.cmd < 2),
            Assume(dram_wait.r   < 2),
            Assume(dram_wait.w   < 2),
        ]

        return m


class WritebackCacheTestCase(FormalTestCase):
    def test_wrong_dram_port(self):
        with self.assertRaisesRegex(TypeError,
                r"DRAM port must be an instance of lambdasoc\.cores\.litedram\.NativePort, "
                r"not 'foo'"):
            WritebackCache(dram_port="foo", size=8, data_width=16)

    def test_wrong_size(self):
        dram_port = litedram.NativePort(addr_width=23, data_width=32)
        with self.assertRaisesRegex(ValueError,
                r"Cache size must be a positive power of two integer, not 'foo'"):
            WritebackCache(dram_port, size="foo", data_width=16)
        with self.assertRaisesRegex(ValueError,
                r"Cache size must be a positive power of two integer, not -1"):
            WritebackCache(dram_port, size=-1, data_width=16)
        with self.assertRaisesRegex(ValueError,
                r"Cache size must be a positive power of two integer, not 42"):
            WritebackCache(dram_port, size=42, data_width=16)

    def test_wrong_data_width(self):
        dram_port = litedram.NativePort(addr_width=23, data_width=32)
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive power of two integer, not 'foo'"):
            WritebackCache(dram_port, size=8, data_width="foo")
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive power of two integer, not -1"):
            WritebackCache(dram_port, size=8, data_width=-1)
        with self.assertRaisesRegex(ValueError,
                r"Data width must be a positive power of two integer, not 42"):
            WritebackCache(dram_port, size=8, data_width=42)

    def test_wrong_ratio(self):
        dram_port = litedram.NativePort(addr_width=23, data_width=32)
        with self.assertRaisesRegex(ValueError,
                r"DRAM port data width must be a multiple of data width, but 32 is not a multiple "
                r"of 64"):
            WritebackCache(dram_port, size=8, data_width=64)

    def check(self, dut):
        m = Module()
        m.domains.sync = ClockDomain(reset_less=True)
        m.submodules.spec = WritebackCacheSpec(dut)
        self.assertFormal(m, mode="hybrid", depth=10)

    def test_spec_simple(self):
        dram_port = litedram.NativePort(addr_width=23, data_width=32)
        dut = WritebackCache(dram_port, size=8, data_width=16, granularity=8)
        self.check(dut)


class SDRAMPeripheralTestCase(unittest.TestCase):
    def test_wrong_core(self):
        with self.assertRaisesRegex(TypeError,
                r"LiteDRAM core must be an instance of lambdasoc\.cores\.litedram\.Core, "
                r"not 'foo'"):
            sdram = SDRAMPeripheral(core="foo", cache_size=8)
