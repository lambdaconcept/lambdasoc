import argparse
import importlib

from nmigen import *
from nmigen.back import rtlil
from nmigen_soc import wishbone

from lambdasoc.cpu.minerva import MinervaCPU
from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.soc.cpu import CPUSoC


__all__ = ["SRAMSoC"]


class SRAMSoC(CPUSoC, Elaboratable):
    def __init__(self, *, reset_addr, clk_freq,
                 rom_addr, rom_size,
                 ram_addr, ram_size,
                 uart_addr, uart_divisor, uart_pins, uart_model,
                 timer_addr, timer_width):
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.cpu = MinervaCPU(reset_address=reset_addr)
        self._arbiter.add(self.cpu.ibus)
        self._arbiter.add(self.cpu.dbus)

        self.rom = SRAMPeripheral(size=rom_size, writable=False)
        self._decoder.add(self.rom.bus, addr=rom_addr)

        self.ram = SRAMPeripheral(size=ram_size)
        self._decoder.add(self.ram.bus, addr=ram_addr)

        self.uart = AsyncSerialPeripheral(divisor=uart_divisor, pins=uart_pins, model=uart_model)
        self._decoder.add(self.uart.bus, addr=uart_addr)

        self.timer = TimerPeripheral(width=timer_width)
        self._decoder.add(self.timer.bus, addr=timer_addr)

        self.intc = GenericInterruptController(width=len(self.cpu.ip))
        self.intc.add_irq(self.timer.irq, 0)
        self.intc.add_irq(self.uart .irq, 1)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.arbiter = self._arbiter
        m.submodules.cpu     = self.cpu

        m.submodules.decoder = self._decoder
        m.submodules.rom     = self.rom
        m.submodules.ram     = self.ram
        m.submodules.uart    = self.uart
        m.submodules.timer   = self.timer
        m.submodules.intc    = self.intc

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ip.eq(self.intc.ip),
        ]

        return m


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", type=str,
            help="target platform (e.g. 'nmigen_boards.arty_a7.ArtyA7Platform')")
    parser.add_argument("--baudrate", type=int,
            default=9600,
            help="UART baudrate (default: 9600)")
    args = parser.parse_args()

    if args.platform is not None:
        def get_platform(platform_name):
            module_name, class_name = platform_name.rsplit(".", 1)
            module = importlib.import_module(name=module_name)
            platform_class = getattr(module, class_name)
            return platform_class()

        platform   = get_platform(args.platform)
        clk_freq   = int(platform.default_clk_frequency)
        uart_pins  = platform.request("uart", 0)
        uart_model = False
    else:
        platform   = None
        clk_freq   = int(1e6)
        uart_pins  = None
        uart_model = True

    soc = SRAMSoC(
         reset_addr=0x00000000, clk_freq=clk_freq,
           rom_addr=0x00000000, rom_size=0x4000,
           ram_addr=0x00004000, ram_size=0x1000,
          uart_addr=0x00005000, uart_divisor=int(clk_freq // args.baudrate),
                                uart_pins=uart_pins, uart_model=uart_model,
         timer_addr=0x00006000, timer_width=32,
    )

    soc.build(do_build=True, do_init=True)

    if platform is not None:
        platform.build(soc, do_program=True)
    else:
        # Build with the write_cxxrtl Yosys backend:
        # python sram_soc.py > sram_soc.il
        # yosys sram_soc.il -o sram_soc.cc
        # clang++ -I/usr/local/share/yosys/include/backends/cxxrtl -luv -O2 sram_soc_driver.cc -o sram_soc_driver
        ports = [
            soc.uart._phy.rx.data, soc.uart._phy.rx.ack, soc.uart._phy.rx.rdy,
            soc.uart._phy.tx.data, soc.uart._phy.tx.ack, soc.uart._phy.tx.rdy,
        ]
        print(rtlil.convert(soc, ports=ports))
