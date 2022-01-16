from amaranth import *
from amaranth.asserts import *
from amaranth.utils import log2_int

from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth_soc.periph import ConstantMap

from . import Peripheral

from ..cores import litedram


__all__ = ["WritebackCache", "SDRAMPeripheral"]


class WritebackCache(Elaboratable):
    """Write-back cache.

    A write-back cache designed to bridge the SoC interconnect to LiteDRAM.

    Parameters
    ----------
    dram_port : :class:`litedram.NativePort`
        LiteDRAM user port.
    size : int
        Cache size.
    data_width : int
        Initiator bus data width.
    granularity : int
        Initiator bus granularity.
    dirty_init : bool
        Dirty initialization. Defaults to ``False``. May be useful for simulation.

    Attributes
    ----------
    intr_bus : :class:`amaranth_soc.wishbone.Interface`
        Initiator bus, with support for incremental bursts.
    """
    def __init__(self, dram_port, *, size, data_width, granularity=None, dirty_init=False):
        if not isinstance(dram_port, litedram.NativePort):
            raise TypeError("DRAM port must be an instance of lambdasoc.cores.litedram.NativePort, "
                            "not {!r}"
                            .format(dram_port))
        if not isinstance(size, int) or size <= 0 or size & size - 1:
            raise ValueError("Cache size must be a positive power of two integer, not {!r}"
                             .format(size))
        if not isinstance(data_width, int) or data_width <= 0 or data_width & data_width - 1:
            raise ValueError("Data width must be a positive power of two integer, not {!r}"
                             .format(data_width))
        if dram_port.data_width % data_width != 0:
            raise ValueError("DRAM port data width must be a multiple of data width, but {} is "
                             "not a multiple of {}"
                             .format(dram_port.data_width, data_width))

        self.intr_bus  = wishbone.Interface(
            addr_width  = dram_port.addr_width + log2_int(dram_port.data_width // data_width),
            data_width  = data_width,
            granularity = granularity,
            features    = {"cti", "bte"},
        )
        intr_map = MemoryMap(
            addr_width = self.intr_bus.addr_width + log2_int(data_width // granularity),
            data_width = granularity,
        )
        try:
            intr_map.add_window(dram_port.memory_map)
        except AttributeError:
            pass
        self.intr_bus.memory_map = intr_map

        self.dram_port = dram_port
        self.size      = size

        self.dirty_init = bool(dirty_init)

    def elaborate(self, platform):
        m = Module()

        ratio    = self.dram_port.data_width // self.intr_bus.data_width
        nb_lines = (self.size * self.intr_bus.granularity) // self.dram_port.data_width

        intr_adr = Record([
            ("offset", log2_int(ratio)),
            ("line",   log2_int(nb_lines)),
            ("tag",    len(self.intr_bus.adr) - log2_int(nb_lines) - log2_int(ratio)),
        ])
        m.d.comb += intr_adr.eq(self.intr_bus.adr),

        intr_adr_next = Record.like(intr_adr)

        with m.Switch(self.intr_bus.bte):
            with m.Case(wishbone.BurstTypeExt.LINEAR):
                m.d.comb += intr_adr_next.eq(intr_adr + 1)
            with m.Case(wishbone.BurstTypeExt.WRAP_4):
                m.d.comb += intr_adr_next[:2].eq(intr_adr[:2] + 1)
                m.d.comb += intr_adr_next[2:].eq(intr_adr[2:])
            with m.Case(wishbone.BurstTypeExt.WRAP_8):
                m.d.comb += intr_adr_next[:3].eq(intr_adr[:3] + 1)
                m.d.comb += intr_adr_next[3:].eq(intr_adr[3:])
            with m.Case(wishbone.BurstTypeExt.WRAP_16):
                m.d.comb += intr_adr_next[:4].eq(intr_adr[:4] + 1)
                m.d.comb += intr_adr_next[4:].eq(intr_adr[4:])

        tag_rp_data = Record([
            ("tag",   intr_adr.tag.shape()),
            ("dirty", 1),
        ])
        tag_wp_data = Record.like(tag_rp_data)

        tag_mem = Memory(width=len(tag_rp_data), depth=nb_lines)
        if self.dirty_init:
            tag_mem.init = [-1 for _ in range(nb_lines)]

        m.submodules.tag_rp = tag_rp = tag_mem.read_port(transparent=False)
        m.submodules.tag_wp = tag_wp = tag_mem.write_port()
        tag_rp.en.reset = 0

        m.d.comb += [
            tag_rp_data.eq(tag_rp.data),
            tag_wp.data.eq(tag_wp_data),
        ]

        dat_mem = Memory(width=self.dram_port.data_width, depth=nb_lines)
        m.submodules.dat_rp = dat_rp = dat_mem.read_port(transparent=False)
        m.submodules.dat_wp = dat_wp = dat_mem.write_port(granularity=self.intr_bus.granularity)
        dat_rp.en.reset = 0

        intr_bus_r = Record.like(self.intr_bus)
        intr_adr_r = Record.like(intr_adr)
        m.d.comb += intr_adr_r.eq(intr_bus_r.adr)

        with m.FSM() as fsm:
            with m.State("CHECK"):
                m.d.sync += [
                    intr_bus_r.cyc.eq(self.intr_bus.cyc),
                    intr_bus_r.stb.eq(self.intr_bus.stb),
                    intr_bus_r.adr.eq(self.intr_bus.adr),
                ]
                # Tag/Data memory read
                with m.If(self.intr_bus.cyc & self.intr_bus.stb):
                    with m.If(self.intr_bus.ack & (self.intr_bus.cti == wishbone.CycleType.INCR_BURST)):
                        m.d.comb += [
                            tag_rp.addr.eq(intr_adr_next.line),
                            dat_rp.addr.eq(intr_adr_next.line),
                        ]
                    with m.Else():
                        m.d.comb += [
                            tag_rp.addr.eq(intr_adr.line),
                            dat_rp.addr.eq(intr_adr.line),
                        ]
                    with m.If(~intr_bus_r.cyc | ~intr_bus_r.stb | self.intr_bus.ack):
                        m.d.comb += [
                            tag_rp.en.eq(1),
                            dat_rp.en.eq(1),
                        ]
                m.d.comb += [
                    self.intr_bus.dat_r.eq(
                        dat_rp.data.word_select(intr_adr.offset, len(self.intr_bus.dat_r))
                    ),
                ]
                # Tag/Data memory write
                m.d.comb += [
                    tag_wp.addr      .eq(intr_adr.line),
                    tag_wp_data.tag  .eq(intr_adr.tag),
                    tag_wp_data.dirty.eq(1),
                    dat_wp.addr      .eq(intr_adr.line),
                    dat_wp.data      .eq(Repl(self.intr_bus.dat_w, ratio)),
                ]
                with m.If(self.intr_bus.cyc & self.intr_bus.stb):
                    with m.If(intr_adr.tag == tag_rp_data.tag):
                        m.d.comb += self.intr_bus.ack.eq(intr_bus_r.cyc & intr_bus_r.stb)
                        with m.If(self.intr_bus.we & self.intr_bus.ack):
                            m.d.comb += [
                                tag_wp.en.eq(1),
                                dat_wp.en.word_select(intr_adr.offset, len(self.intr_bus.sel)).eq(self.intr_bus.sel),
                            ]
                    with m.Elif(intr_bus_r.cyc & intr_bus_r.stb):
                        m.d.sync += [
                            intr_bus_r.cyc.eq(0),
                            intr_bus_r.stb.eq(0),
                        ]
                        with m.If(tag_rp_data.dirty):
                            m.next = "EVICT"
                        with m.Else():
                            m.next = "REFILL"

            with m.State("EVICT"):
                evict_done = Record([("cmd", 1), ("w", 1)])
                with m.If(evict_done.all()):
                    m.d.sync += evict_done.eq(0)
                    m.next = "REFILL"
                # Command
                m.d.comb += [
                    self.dram_port.cmd.valid.eq(~evict_done.cmd),
                    self.dram_port.cmd.last .eq(0),
                    self.dram_port.cmd.addr .eq(Cat(intr_adr_r.line, tag_rp_data.tag)),
                    self.dram_port.cmd.we   .eq(1),
                ]
                with m.If(self.dram_port.cmd.valid & self.dram_port.cmd.ready):
                    m.d.sync += evict_done.cmd.eq(1)
                # Write
                m.d.comb += [
                    self.dram_port.w.valid.eq(~evict_done.w),
                    self.dram_port.w.we   .eq(Repl(Const(1), self.dram_port.data_width // 8)),
                    self.dram_port.w.data .eq(dat_rp.data),
                ]
                with m.If(self.dram_port.w.valid & self.dram_port.w.ready):
                    m.d.sync += evict_done.w.eq(1)

            with m.State("REFILL"):
                refill_done = Record([("cmd", 1), ("r", 1)])
                with m.If(refill_done.all()):
                    m.d.sync += refill_done.eq(0)
                    m.next = "CHECK"
                # Command
                m.d.comb += [
                    self.dram_port.cmd.valid.eq(~refill_done.cmd),
                    self.dram_port.cmd.last .eq(1),
                    self.dram_port.cmd.addr .eq(Cat(intr_adr_r.line, intr_adr_r.tag)),
                    self.dram_port.cmd.we   .eq(0),
                ]
                with m.If(self.dram_port.cmd.valid & self.dram_port.cmd.ready):
                    m.d.sync += refill_done.cmd.eq(1)
                # Read
                m.d.comb += [
                    self.dram_port.r.ready.eq(~refill_done.r),
                    tag_wp.addr      .eq(intr_adr_r.line),
                    tag_wp.en        .eq((self.dram_port.r.valid & self.dram_port.r.ready)),
                    tag_wp_data.tag  .eq(intr_adr_r.tag),
                    tag_wp_data.dirty.eq(0),
                    dat_wp.addr      .eq(intr_adr_r.line),
                    dat_wp.en        .eq(Repl((self.dram_port.r.valid & self.dram_port.r.ready), len(dat_wp.en))),
                    dat_wp.data      .eq(self.dram_port.r.data),
                ]
                with m.If(self.dram_port.r.valid & self.dram_port.r.ready):
                    m.d.sync += refill_done.r.eq(1)

        if platform == "formal":
            with m.If(Initial()):
                m.d.comb += [
                    Assume(fsm.ongoing("CHECK")),
                    Assume(~intr_bus_r.cyc),
                    Assume(~evict_done.any()),
                    Assume(~refill_done.any()),
                ]

        return m


class SDRAMPeripheral(Peripheral, Elaboratable):
    """SDRAM controller peripheral.

    Parameters
    ----------
    core : :class:`litedram.Core`
        LiteDRAM core.
    cache_size : int
        Cache size, in bytes.
    cache_dirty_init : boot
        Initialize cache as dirty. Defaults to `False`.
    """
    def __init__(self, *, core, cache_size, cache_dirty_init=False):
        super().__init__()

        if not isinstance(core, litedram.Core):
            raise TypeError("LiteDRAM core must be an instance of lambdasoc.cores.litedram.Core, "
                            "not {!r}"
                            .format(core))
        self.core = core

        data_width       = core.ctrl_bus.data_width
        granularity      = core.ctrl_bus.granularity
        granularity_bits = log2_int(data_width // granularity)

        # Data path : bridge -> cache -> LiteDRAM user port

        self._data_bus = self.window(
            addr_width  = core.user_port.addr_width
                        + log2_int(core.user_port.data_width // 8)
                        - granularity_bits,
            data_width  = data_width,
            granularity = granularity,
            features    = {"cti", "bte"},
        )
        data_map = MemoryMap(
            addr_width = self._data_bus.addr_width + granularity_bits,
            data_width = granularity,
            alignment  = 0,
        )

        self._cache = WritebackCache(
            core.user_port,
            size        = cache_size,
            data_width  = data_width,
            granularity = granularity,
            dirty_init  = cache_dirty_init,
        )
        data_map.add_window(self._cache.intr_bus.memory_map)

        self._data_bus.memory_map = data_map

        # Control path : bridge -> LiteDRAM control port

        self._ctrl_bus = self.window(
            addr_width  = core._ctrl_bus.addr_width,
            data_width  = data_width,
            granularity = granularity,
            addr        = core.size,
        )
        ctrl_map = MemoryMap(
            addr_width = self._ctrl_bus.addr_width + granularity_bits,
            data_width = granularity,
            alignment  = 0,
        )

        ctrl_map.add_window(core.ctrl_bus.memory_map)

        self._ctrl_bus.memory_map = ctrl_map

        self._bridge = self.bridge(data_width=data_width, granularity=granularity)
        self.bus     = self._bridge.bus

    @property
    def constant_map(self):
        return ConstantMap(
            SIZE       = self.core.size,
            CACHE_SIZE = self._cache.size,
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules.bridge = self._bridge
        m.submodules.cache  = self._cache
        m.submodules.core   = self.core

        m.d.comb += [
            self._cache.intr_bus.adr  .eq(self._data_bus.adr),
            self._cache.intr_bus.cyc  .eq(self._data_bus.cyc),
            self._cache.intr_bus.stb  .eq(self._data_bus.stb),
            self._cache.intr_bus.sel  .eq(self._data_bus.sel),
            self._cache.intr_bus.we   .eq(self._data_bus.we),
            self._cache.intr_bus.dat_w.eq(self._data_bus.dat_w),
            self._cache.intr_bus.cti  .eq(self._data_bus.cti),
            self._cache.intr_bus.bte  .eq(self._data_bus.bte),
            self._data_bus.ack  .eq(self._cache.intr_bus.ack),
            self._data_bus.dat_r.eq(self._cache.intr_bus.dat_r),

            self.core.ctrl_bus.adr  .eq(self._ctrl_bus.adr),
            self.core.ctrl_bus.cyc  .eq(self._ctrl_bus.cyc),
            self.core.ctrl_bus.stb  .eq(self._ctrl_bus.stb),
            self.core.ctrl_bus.sel  .eq(self._ctrl_bus.sel),
            self.core.ctrl_bus.we   .eq(self._ctrl_bus.we),
            self.core.ctrl_bus.dat_w.eq(self._ctrl_bus.dat_w),
            self._ctrl_bus.ack  .eq(self.core.ctrl_bus.ack),
            self._ctrl_bus.dat_r.eq(self.core.ctrl_bus.dat_r),
        ]

        return m
