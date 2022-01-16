from amaranth import *
from amaranth.lib.fifo import SyncFIFOBuffered

from amaranth_soc.periph import ConstantMap

from amaranth_stdio.serial import AsyncSerial

from . import Peripheral
from ..sim.blackboxes.serial.wrapper import AsyncSerial_Blackbox


__all__ = ["AsyncSerialPeripheral"]


class AsyncSerialPeripheral(Peripheral, Elaboratable):
    """Asynchronous serial transceiver peripheral.

    See :class:`amaranth_stdio.serial.AsyncSerial` for details.

    Notes
    -----

    * If this peripheral is used with the LambdaSoC BIOS, `rx_depth * data_bits` should be at least
    256 bytes in order to buffer a complete SFL frame. Otherwise, a race condition may occur during
    a serialboot at high baudrates.

    CSR registers
    -------------
    divisor : read/write
        Clock divisor.
    rx_data : read-only
        Receiver data.
    rx_rdy : read-only
        Receiver ready. The receiver FIFO is non-empty.
    rx_err : read-only
        Receiver error flags. See :class:`amaranth_stdio.serial.AsyncSerialRX` for layout.
    tx_data : write-only
        Transmitter data.
    tx_rdy : read-only
        Transmitter ready. The transmitter FIFO is non-full.

    Events
    ------
    rx_rdy : level-triggered
        Receiver ready. The receiver FIFO is non-empty.
    rx_err : edge-triggered (rising)
        Receiver error. Error cause is available in the ``rx_err`` register.
    tx_mty : edge-triggered (rising)
        Transmitter empty. The transmitter FIFO is empty.

    Parameters
    ----------
    rx_depth : int
        Depth of the receiver FIFO.
    tx_depth : int
        Depth of the transmitter FIFO.
    divisor : int
        Clock divisor reset value. Should be set to ``int(clk_frequency // baudrate)``.
    divisor_bits : int
        Optional. Clock divisor width. If omitted, ``bits_for(divisor)`` is used instead.
    data_bits : int
        Data width.
    parity : ``"none"``, ``"mark"``, ``"space"``, ``"even"``, ``"odd"``
        Parity mode.
    pins : :class:`Record`
        Optional. UART pins. See :class:`amaranth_boards.resources.UARTResource`.

    Attributes
    ----------
    bus : :class:`amaranth_soc.wishbone.Interface`
        Wishbone bus interface.
    irq : :class:`IRQLine`
        Interrupt request line.
    """
    def __init__(self, *, core, rx_depth=256, tx_depth=16, **kwargs):
        super().__init__()

        if not isinstance(core, (AsyncSerial, AsyncSerial_Blackbox)):
            raise TypeError("Core must be an instance of AsyncSerial or AsyncSerial_Blackbox, "
                            "not {!r}".format(core))
        self._phy       = core
        self._rx_fifo   = SyncFIFOBuffered(width=self._phy.rx.data.width, depth=rx_depth)
        self._tx_fifo   = SyncFIFOBuffered(width=self._phy.tx.data.width, depth=tx_depth)

        bank            = self.csr_bank()
        self._divisor   = bank.csr(self._phy.divisor.width, "rw")
        self._rx_data   = bank.csr(self._phy.rx.data.width, "r")
        self._rx_rdy    = bank.csr(1, "r")
        self._rx_err    = bank.csr(len(self._phy.rx.err),   "r")
        self._tx_data   = bank.csr(self._phy.tx.data.width, "w")
        self._tx_rdy    = bank.csr(1, "r")

        self._rx_rdy_ev = self.event(mode="level")
        self._rx_err_ev = self.event(mode="rise")
        self._tx_mty_ev = self.event(mode="rise")

        self._bridge    = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus        = self._bridge.bus
        self.irq        = self._bridge.irq

    @property
    def constant_map(self):
        return ConstantMap(
            RX_DEPTH = self._rx_fifo.depth,
            TX_DEPTH = self._tx_fifo.depth,
        )

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge  = self._bridge

        m.submodules.phy     = self._phy
        m.submodules.rx_fifo = self._rx_fifo
        m.submodules.tx_fifo = self._tx_fifo

        m.d.comb += self._divisor.r_data.eq(self._phy.divisor)
        with m.If(self._divisor.w_stb):
            m.d.sync += self._phy.divisor.eq(self._divisor.w_data)

        m.d.comb += [
            self._rx_data.r_data.eq(self._rx_fifo.r_data),
            self._rx_fifo.r_en.eq(self._rx_data.r_stb),
            self._rx_rdy.r_data.eq(self._rx_fifo.r_rdy),

            self._rx_fifo.w_data.eq(self._phy.rx.data),
            self._rx_fifo.w_en.eq(self._phy.rx.rdy),
            self._phy.rx.ack.eq(self._rx_fifo.w_rdy),
            self._rx_err.r_data.eq(self._phy.rx.err),

            self._tx_fifo.w_en.eq(self._tx_data.w_stb),
            self._tx_fifo.w_data.eq(self._tx_data.w_data),
            self._tx_rdy.r_data.eq(self._tx_fifo.w_rdy),

            self._phy.tx.data.eq(self._tx_fifo.r_data),
            self._phy.tx.ack.eq(self._tx_fifo.r_rdy),
            self._tx_fifo.r_en.eq(self._phy.tx.rdy),

            self._rx_rdy_ev.stb.eq(self._rx_fifo.r_rdy),
            self._rx_err_ev.stb.eq(self._phy.rx.err.any()),
            self._tx_mty_ev.stb.eq(~self._tx_fifo.r_rdy),
        ]

        return m
