import argparse
import importlib

from nmigen import *
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
                 uart_addr, uart_divisor, uart_pins,
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

        self.uart = AsyncSerialPeripheral(divisor=uart_divisor, pins=uart_pins)
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
    parser.add_argument("platform", type=str,
            help="target platform (e.g. 'nmigen_boards.arty_a7.ArtyA7Platform')")
    parser.add_argument("--baudrate", type=int,
            default=9600,
            help="UART baudrate (default: 9600)")
    parser.add_argument("--build-dir", type=str,
            default="build",
            help="local build directory (default: 'build')")
    args = parser.parse_args()

    def get_platform(platform_name):
        module_name, class_name = platform_name.rsplit(".", 1)
        module = importlib.import_module(name=module_name)
        platform_class = getattr(module, class_name)
        return platform_class()

    platform = get_platform(args.platform)

    uart_divisor = int(platform.default_clk_frequency // args.baudrate)
    uart_pins = platform.request("uart", 0)

    soc = SRAMSoC(
         reset_addr=0x00000000, clk_freq=int(platform.default_clk_frequency),
           rom_addr=0x00000000, rom_size=0x4000,
           ram_addr=0x00004000, ram_size=0x1000,
          uart_addr=0x00005000, uart_divisor=uart_divisor, uart_pins=uart_pins,
         timer_addr=0x00006000, timer_width=32,
    )

    soc.build(build_dir=f"{args.build_dir}/soc", do_init=True)

    platform.build(soc, build_dir=args.build_dir, do_program=True)
