from amaranth import *
from amaranth.asserts import *

from amaranth_soc import wishbone


__all__ = ["wb_read", "wb_write", "WishboneSubordinateSpec"]


def wb_read(bus, addr, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.sel.eq(sel)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    data = (yield bus.dat_r)
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    return data


def wb_write(bus, addr, data, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.we.eq(1)
    yield bus.sel.eq(sel)
    yield bus.dat_w.eq(data)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.we.eq(0)


class WishboneSubordinateSpec(Elaboratable):
    def __init__(self, bus):
        if not isinstance(bus, wishbone.Interface):
            raise TypeError("Bus must be an instance of wishbone.Interface, not {!r}"
                            .format(bus))
        self.bus = bus

    def elaborate(self, platform):
        m = Module()

        with m.If(Initial()):
            m.d.comb += [
                Assume(~self.bus.cyc),
                Assume(~self.bus.stb),
                Assert(~self.bus.ack),
            ]

        with m.If(~self.bus.cyc & ~Past(self.bus.cyc)):
            m.d.comb += Assert(~self.bus.ack)

        with m.If(Past(self.bus.cyc) & Past(self.bus.stb)):
            # Assume that input signals are held until the transaction is acknowledged.
            with m.If(~Past(self.bus.ack)):
                m.d.comb += [
                    Assume(self.bus.adr   == Past(self.bus.adr)),
                    Assume(self.bus.we    == Past(self.bus.we)),
                    Assume(self.bus.dat_w == Past(self.bus.dat_w)),
                    Assume(self.bus.sel   == Past(self.bus.sel)),
                ]
                if hasattr(self.bus, "cti"):
                    m.d.comb += Assume(self.bus.cti == Past(self.bus.cti))
                if hasattr(self.bus, "bte"):
                    m.d.comb += Assume(self.bus.bte == Past(self.bus.bte))

            if hasattr(self.bus, "cti"):
                # The previous transaction was acknowledged, and this is an incrementing burst.
                with m.Elif(Past(self.bus.cti) == wishbone.CycleType.INCR_BURST):
                    if hasattr(self.bus, "bte"):
                        with m.Switch(self.bus.bte):
                            with m.Case(wishbone.BurstTypeExt.LINEAR):
                                m.d.comb += Assume(self.bus.adr == Past(self.bus.adr) + 1)
                            with m.Case(wishbone.BurstTypeExt.WRAP_4):
                                m.d.comb += [
                                    Assume(self.bus.adr[:2] == Past(self.bus.adr)[:2] + 1),
                                    Assume(self.bus.adr[2:] == Past(self.bus.adr)[2:]),
                                ]
                            with m.Case(wishbone.BurstTypeExt.WRAP_8):
                                m.d.comb += [
                                    Assume(self.bus.adr[:3] == Past(self.bus.adr)[:3] + 1),
                                    Assume(self.bus.adr[3:] == Past(self.bus.adr)[3:]),
                                ]
                            with m.Case(wishbone.BurstTypeExt.WRAP_16):
                                m.d.comb += [
                                    Assume(self.bus.adr[:4] == Past(self.bus.adr)[:4] + 1),
                                    Assume(self.bus.adr[4:] == Past(self.bus.adr)[4:]),
                                ]
                    else:
                        m.d.comb += Assume(self.bus.adr == Past(self.bus.adr) + 1)

            # The previous transaction was acknowledged, and this is either not a burst, or the
            # end of a burst.
            with m.Else():
                m.d.comb += Assume(~self.bus.cyc)

        return m
