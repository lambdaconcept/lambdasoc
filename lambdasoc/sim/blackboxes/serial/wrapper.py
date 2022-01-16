from amaranth import *
from amaranth.utils import bits_for


__all__ = ["AsyncSerialRX_Blackbox", "AsyncSerialTX_Blackbox", "AsyncSerial_Blackbox"]


class AsyncSerialRX_Blackbox(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, data_bits=8, parity="none", parent=None):
        if parent is not None and not isinstance(parent, AsyncSerial_Blackbox):
            raise TypeError("Parent must be an instance of AsyncSerial_Blackbox, not {!r}"
                            .format(parent))
        self.parent = parent

        self.divisor = Signal(divisor_bits or bits_for(divisor))

        self.data = Signal(data_bits)
        self.err  = Record([
            ("overflow", 1),
            ("frame",    1),
            ("parity",   1),
        ])
        self.rdy  = Signal()
        self.ack  = Signal()

    def elaborate(self, platform):
        return Instance("serial_rx",
            p_ID           = hex(id(self.parent) if self.parent else id(self)),
            p_DATA_BITS    = len(self.data),
            i_clk          = ClockSignal("sync"),
            o_data         = self.data,
            o_err_overflow = self.err.overflow,
            o_err_frame    = self.err.frame,
            o_err_parity   = self.err.parity,
            o_rdy          = self.rdy,
            i_ack          = self.ack,
        )


class AsyncSerialTX_Blackbox(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, data_bits=8, parity="none", parent=None):
        if parent is not None and not isinstance(parent, AsyncSerial_Blackbox):
            raise TypeError("Parent must be an instance of AsyncSerial_Blackbox, not {!r}"
                            .format(parent))
        self._parent = parent

        self.divisor = Signal(divisor_bits or bits_for(divisor))

        self.data = Signal(data_bits)
        self.rdy  = Signal()
        self.ack  = Signal()

    def elaborate(self, platform):
        return Instance("serial_tx",
            p_ID        = hex(id(self._parent) if self._parent else id(self)),
            p_DATA_BITS = len(self.data),
            i_clk       = ClockSignal("sync"),
            i_data      = self.data,
            o_rdy       = self.rdy,
            i_ack       = self.ack,
        )


class AsyncSerial_Blackbox(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, **kwargs):
        self.divisor = Signal(divisor_bits or bits_for(divisor), reset=divisor)

        self.rx = AsyncSerialRX_Blackbox(
            divisor      = divisor,
            divisor_bits = divisor_bits,
            parent       = self,
            **kwargs
        )
        self.tx = AsyncSerialTX_Blackbox(
            divisor      = divisor,
            divisor_bits = divisor_bits,
            parent       = self,
            **kwargs
        )

    def elaborate(self, platform):
        m = Module()
        m.submodules.rx = self.rx
        m.submodules.tx = self.tx
        m.d.comb += [
            self.rx.divisor.eq(self.divisor),
            self.tx.divisor.eq(self.divisor),
        ]
        return m
