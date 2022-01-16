from amaranth import *
from amaranth_soc import wishbone
from amaranth_soc.periph import ConstantMap

from minerva.core import Minerva

from . import CPU

from ..soc.cpu import ConstantAddr


__all__ = ["MinervaCPU"]


class MinervaCPU(CPU, Elaboratable):
    name       = "minerva"
    arch       = "riscv"
    byteorder  = "little"
    data_width = 32

    def __init__(self, **kwargs):
        super().__init__()
        self._cpu = Minerva(**kwargs)
        self.ibus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})
        self.dbus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})
        self.ip   = Signal.like(self._cpu.external_interrupt)

    @property
    def reset_addr(self):
        return self._cpu.reset_address

    @property
    def muldiv(self):
        return "hard" if self._cpu.with_muldiv else "soft"

    @property
    def constant_map(self):
        return ConstantMap(
            MINERVA           = True,
            RESET_ADDR        = ConstantAddr(self.reset_addr),
            ARCH_RISCV        = True,
            RISCV_MULDIV_SOFT = self.muldiv == "soft",
            BYTEORDER_LITTLE  = True,
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules.minerva = self._cpu
        m.d.comb += [
            self._cpu.ibus.connect(self.ibus),
            self._cpu.dbus.connect(self.dbus),
            self._cpu.external_interrupt.eq(self.ip),
        ]

        return m
