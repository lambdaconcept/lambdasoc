from ipaddress import IPv4Address

from amaranth import *

from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth_soc.periph import ConstantMap

from . import Peripheral
from .event import IRQLine

from ..cores import liteeth
from ..soc.base import ConstantAddr


__all__ = ["EthernetMACPeripheral"]


class EthernetMACPeripheral(Peripheral, Elaboratable):
    """Ethernet MAC peripheral.

    Parameters
    ----------
    core : :class:`liteeth.Core`
        LiteEth core.
    local_ip : :class:`ipaddress.IPv4Address`
        Local IP address. Defaults to 192.168.1.50.
    remote_ip : :class:`ipaddress.IPv4Address`
        Remote IP address. Defaults to 192.168.1.100.
    """
    def __init__(self, *, core, local_ip="192.168.1.50", remote_ip="192.168.1.100"):
        super().__init__()

        if not isinstance(core, liteeth.Core):
            raise TypeError("LiteEth core must be an instance of lambdasoc.cores.liteeth.Core, "
                            "not {!r}"
                            .format(core))

        self.core      = core
        self.local_ip  = IPv4Address(local_ip)
        self.remote_ip = IPv4Address(remote_ip)

        bus_map = MemoryMap(
            name       = self.name,
            addr_width = core.bus.memory_map.addr_width,
            data_width = core.bus.memory_map.data_width,
        )
        bus_map.add_window(core.bus.memory_map)

        self.bus = wishbone.Interface(
            addr_width  = core.bus.addr_width,
            data_width  = core.bus.data_width,
            granularity = core.bus.granularity,
            features    = {"cti", "bte", "err"},
        )
        self.bus.memory_map = bus_map

        self.irq = IRQLine(name=f"{self.name}_irq")

    @property
    def constant_map(self):
        return ConstantMap(
            CTRL_OFFSET = ConstantAddr(self.core.config.ctrl_addr),
            DATA_OFFSET = ConstantAddr(self.core.config.data_addr),
            RX_SLOTS    = self.core.config.rx_slots,
            TX_SLOTS    = self.core.config.tx_slots,
            SLOT_SIZE   = 2048,
            LOCAL_IP    = int(self.local_ip),
            REMOTE_IP   = int(self.remote_ip),
        )

    def elaborate(self, platform):
        m = Module()
        m.submodules.core = self.core
        m.d.comb += [
            self.bus.connect(self.core.bus),
            self.irq.eq(self.core.irq),
        ]
        return m
