import argparse
from collections import OrderedDict

from amaranth import *
from amaranth.lib.cdc import ResetSynchronizer
from amaranth.build import *

from amaranth_soc import wishbone
from amaranth_soc.periph import ConstantMap

from amaranth_stdio.serial import AsyncSerial

from amaranth_boards.arty_a7 import ArtyA7_35Platform
from amaranth_boards.ecpix5 import ECPIX545Platform, ECPIX585Platform

from lambdasoc.cpu.minerva import MinervaCPU
from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.periph.sdram import SDRAMPeripheral
from lambdasoc.periph.eth import EthernetMACPeripheral

from lambdasoc.soc.cpu import CPUSoC, BIOSBuilder

from lambdasoc.cores.pll.lattice_ecp5 import PLL_LatticeECP5
from lambdasoc.cores.pll.xilinx_7series import PLL_Xilinx7Series
from lambdasoc.cores import litedram, liteeth
from lambdasoc.cores.utils import request_bare

from lambdasoc.sim.blackboxes.serial import AsyncSerial_Blackbox
from lambdasoc.sim.platform import CXXRTLPlatform


__all__ = ["MinervaSoC"]


class _ClockResetGenerator(Elaboratable):
    def __init__(self, *, sync_clk_freq, with_sdram, with_ethernet):
        if not isinstance(sync_clk_freq, (int, float)) or sync_clk_freq <= 0:
            raise ValueError("Sync domain clock frequency must be a positive integer or float, "
                             "not {!r}"
                             .format(sync_clk_freq))
        self.sync_clk_freq = sync_clk_freq
        self.with_sdram    = bool(with_sdram)
        self.with_ethernet = bool(with_ethernet)

    def elaborate(self, platform):
        m = Module()

        m.domains += [
            ClockDomain("_ref", reset_less=platform.default_rst is None, local=True),
            ClockDomain("sync"),
        ]

        m.d.comb += ClockSignal("_ref").eq(platform.request(platform.default_clk, 0).i)
        if platform.default_rst is not None:
            m.d.comb += ResetSignal("_ref").eq(platform.request(platform.default_rst, 0).i)

        # On the Arty A7, the DP83848 Ethernet PHY uses a 25 MHz reference clock.
        if isinstance(platform, ArtyA7_35Platform) and self.with_ethernet:
            m.domains += ClockDomain("_eth_ref", local=True)
            m.submodules += Instance("BUFGCE",
                i_I  = ClockSignal("_eth_ref"),
                i_CE = ~ResetSignal("_eth_ref"),
                o_O  = platform.request("eth_clk25", 0).o,
            )

        # The LiteDRAM core provides its own PLL, which drives the litedram_user clock domain.
        # We reuse this clock domain as the sync domain, in order to avoid CDC between LiteDRAM
        # and the SoC interconnect.
        if self.with_sdram:
            m.domains += ClockDomain("litedram_input")
            m.d.comb += ClockSignal("litedram_input").eq(ClockSignal("_ref"))
            if platform.default_rst is not None:
                m.d.comb += ResetSignal("litedram_input").eq(ResetSignal("_ref"))

            m.domains += ClockDomain("litedram_user")
            m.d.comb += [
                ClockSignal("sync").eq(ClockSignal("litedram_user")),
                ResetSignal("sync").eq(ResetSignal("litedram_user")),
            ]

            # On the Arty A7, we still use our own PLL to drive the Ethernet PHY reference clock.
            if isinstance(platform, ArtyA7_35Platform) and self.with_ethernet:
                eth_ref_pll_params = PLL_Xilinx7Series.Parameters(
                    i_domain     = "_ref",
                    i_freq       = platform.default_clk_frequency,
                    i_reset_less = platform.default_rst is None,
                    o_domain     = "_eth_ref",
                    o_freq       = 25e6,
                )
                m.submodules.eth_ref_pll = eth_ref_pll = PLL_Xilinx7Series(eth_ref_pll_params)

                if platform.default_rst is not None:
                    eth_ref_pll_arst = ~eth_ref_pll.locked | ResetSignal("_ref")
                else:
                    eth_ref_pll_arst = ~eth_ref_pll.locked

                m.submodules += ResetSynchronizer(eth_ref_pll_arst, domain="_eth_ref")

        # In simulation mode, the sync clock domain is directly driven by the platform clock.
        elif isinstance(platform, CXXRTLPlatform):
            assert self.sync_clk_freq == platform.default_clk_frequency
            m.d.comb += ClockSignal("sync").eq(ClockSignal("_ref"))
            if platform.default_rst is not None:
                m.d.comb += ResetSignal("sync").eq(ResetSignal("_ref"))

        # Otherwise, we use a PLL to drive the sync clock domain.
        else:
            if isinstance(platform, ArtyA7_35Platform):
                sync_pll_params = PLL_Xilinx7Series.Parameters(
                    i_domain     = "_ref",
                    i_freq       = platform.default_clk_frequency,
                    i_reset_less = platform.default_rst is None,
                    o_domain     = "sync",
                    o_freq       = self.sync_clk_freq,
                )
                if self.with_ethernet:
                    sync_pll_params.add_secondary_output(domain="_eth_ref", freq=25e6)
                m.submodules.sync_pll = sync_pll = PLL_Xilinx7Series(sync_pll_params)
            elif isinstance(platform, (ECPIX545Platform, ECPIX585Platform)):
                sync_pll_params = PLL_LatticeECP5.Parameters(
                    i_domain     = "_ref",
                    i_freq       = platform.default_clk_frequency,
                    i_reset_less = platform.default_rst is None,
                    o_domain     = "sync",
                    o_freq       = self.sync_clk_freq,
                )
                m.submodules.sync_pll = sync_pll = PLL_LatticeECP5(sync_pll_params)
            else:
                assert False

            if platform.default_rst is not None:
                sync_pll_arst = ~sync_pll.locked | ResetSignal("_ref")
            else:
                sync_pll_arst = ~sync_pll.locked

            m.submodules += ResetSynchronizer(sync_pll_arst, domain="sync")
            if isinstance(platform, ArtyA7_35Platform) and self.with_ethernet:
                m.submodules += ResetSynchronizer(sync_pll_arst, domain="_eth_ref")

        return m


class MinervaSoC(CPUSoC, Elaboratable):
    def __init__(self,
            sync_clk_freq,
            cpu_core,
            bootrom_addr,
            bootrom_size,
            scratchpad_addr,
            scratchpad_size,
            uart_core,
            uart_addr,
            uart_irqno,
            timer_addr,
            timer_width,
            timer_irqno):
        if not isinstance(sync_clk_freq, (int, float)) or sync_clk_freq <= 0:
            raise ValueError("Sync domain clock frequency must be a positive integer or float, "
                             "not {!r}"
                             .format(sync_clk_freq))
        self.sync_clk_freq = int(sync_clk_freq)

        if not isinstance(cpu_core, MinervaCPU):
            raise TypeError("CPU core must be an instance of MinervaCPU, not {!r}"
                            .format(cpu_core))
        self.cpu = cpu_core

        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte", "err"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte", "err"})

        self._arbiter.add(self.cpu.ibus)
        self._arbiter.add(self.cpu.dbus)

        self.intc = GenericInterruptController(width=len(self.cpu.ip))

        self.bootrom = SRAMPeripheral(size=bootrom_size, writable=False)
        self._decoder.add(self.bootrom.bus, addr=bootrom_addr)

        self.scratchpad = SRAMPeripheral(size=scratchpad_size)
        self._decoder.add(self.scratchpad.bus, addr=scratchpad_addr)

        self.uart = AsyncSerialPeripheral(core=uart_core)
        self._decoder.add(self.uart.bus, addr=uart_addr)
        self.intc.add_irq(self.uart.irq, index=uart_irqno)

        self.timer = TimerPeripheral(width=timer_width)
        self._decoder.add(self.timer.bus, addr=timer_addr)
        self.intc.add_irq(self.timer.irq, index=timer_irqno)

        self._sdram  = None
        self._sram   = None
        self._ethmac = None

    @property
    def memory_map(self):
        return self._decoder.bus.memory_map

    @property
    def constants(self):
        return super().constants.union(
            SDRAM  = self.sdram .constant_map if self.sdram  is not None else None,
            ETHMAC = self.ethmac.constant_map if self.ethmac is not None else None,
            SOC    = ConstantMap(
                WITH_SDRAM        = self.sdram  is not None,
                WITH_ETHMAC       = self.ethmac is not None,
                MEMTEST_ADDR_SIZE = 8192,
                MEMTEST_DATA_SIZE = 8192,
            ),
        )

    @property
    def mainram(self):
        assert not (self._sdram and self.sram)
        return self._sdram or self._sram

    @property
    def sdram(self):
        return self._sdram

    @property
    def sram(self):
        return self._sram

    def add_sdram(self, core, *, addr, cache_size):
        if self.mainram is not None:
            raise AttributeError("Main RAM has already been set to {!r}".format(self.mainram))
        if core.config.user_clk_freq != self.sync_clk_freq:
            raise ValueError("LiteDRAM user domain clock frequency ({} MHz) must match sync "
                             "domain clock frequency ({} MHz)"
                             .format(core.config.user_clk_freq / 1e6, self.sync_clk_freq / 1e6))
        self._sdram = SDRAMPeripheral(core=core, cache_size=cache_size)
        self._decoder.add(self._sdram.bus, addr=addr)

    def add_internal_sram(self, *, addr, size):
        if self.mainram is not None:
            raise AttributeError("Main RAM has already been set to {!r}".format(self.mainram))
        self._sram = SRAMPeripheral(size=size)
        self._decoder.add(self._sram.bus, addr=addr)

    @property
    def ethmac(self):
        return self._ethmac

    def add_ethmac(self, core, *, addr, irqno, local_ip, remote_ip):
        if self._ethmac is not None:
            raise AttributeError("Ethernet MAC has already been set to {!r}"
                                 .format(self._ethmac))
        self._ethmac = EthernetMACPeripheral(core=core, local_ip=local_ip, remote_ip=remote_ip)
        self._decoder.add(self._ethmac.bus, addr=addr)
        self.intc.add_irq(self._ethmac.irq, index=irqno)

    def elaborate(self, platform):
        m = Module()

        m.submodules.crg = _ClockResetGenerator(
            sync_clk_freq = self.sync_clk_freq,
            with_sdram    = self.sdram is not None,
            with_ethernet = self.ethmac is not None,
        )

        m.submodules.cpu        = self.cpu
        m.submodules.arbiter    = self._arbiter
        m.submodules.decoder    = self._decoder
        m.submodules.uart       = self.uart
        m.submodules.timer      = self.timer
        m.submodules.intc       = self.intc
        m.submodules.bootrom    = self.bootrom
        m.submodules.scratchpad = self.scratchpad

        if self.sdram is not None:
            m.submodules.sdram = self.sdram
        if self.sram is not None:
            m.submodules.sram = self.sram
        if self.ethmac is not None:
            m.submodules.ethmac = self.ethmac

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ip.eq(self.intc.ip),
        ]

        return m


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=str,
            default="build/minerva_soc",
            help="local build directory (default: 'build/sdram_soc')")
    parser.add_argument("--platform", type=str,
            choices=("sim", "arty_a7", "ecpix5_45", "ecpix5_85"),
            default="sim",
            help="target platform")
    parser.add_argument("--sync-clk-freq", type=int,
            default=75,
            help="SoC clock frequency, in MHz. (default: 75)")
    parser.add_argument("--with-sdram", action="store_true",
            help="enable SDRAM")
    parser.add_argument("--internal-sram-size", type=int,
            default=8192,
            help="Internal RAM size, in bytes. Ignored if --with-sdram is provided. "
                 "(default: 8192)")
    parser.add_argument("--baudrate", type=int,
            default=9600,
            help="UART baudrate (default: 9600)")
    parser.add_argument("--with-ethernet", action="store_true",
            help="enable Ethernet")
    parser.add_argument("--local-ip", type=str,
            default="192.168.1.50",
            help="Local IPv4 address (default: 192.168.1.50)")
    parser.add_argument("--remote-ip", type=str,
            default="192.168.1.100",
            help="Remote IPv4 address (default: 192.168.1.100)")
    args = parser.parse_args()

    # Platform selection

    if args.platform == "sim":
        platform = CXXRTLPlatform()
    elif args.platform == "arty_a7":
        platform = ArtyA7_35Platform()
    elif args.platform == "ecpix5_45":
        platform = ECPIX545Platform()
    elif args.platform == "ecpix5_85":
        platform = ECPIX585Platform()
    else:
        assert False

    # LiteDRAM

    if args.with_sdram:
        if isinstance(platform, CXXRTLPlatform):
            litedram_config = litedram.ECP5Config(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(platform.default_clk_frequency),
                user_clk_freq  = int(platform.default_clk_frequency),
                init_clk_freq  = int(1e6),
            )
        elif isinstance(platform, ArtyA7_35Platform):
            litedram_config = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = 60,
                ron              = 34,
                input_clk_freq   = int(platform.default_clk_frequency),
                user_clk_freq    = int(args.sync_clk_freq * 1e6),
                iodelay_clk_freq = int(200e6),
            )
        elif isinstance(platform, (ECPIX545Platform, ECPIX585Platform)):
            litedram_config = litedram.ECP5Config(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(platform.default_clk_frequency),
                user_clk_freq  = int(args.sync_clk_freq * 1e6),
                init_clk_freq  = int(25e6),
            )
        else:
            assert False

        if isinstance(platform, CXXRTLPlatform):
            litedram_pins = None
        else:
            litedram_pins = request_bare(platform, "ddr3", 0)

        litedram_core = litedram.Core(litedram_config, pins=litedram_pins)
        litedram_core.build(litedram.Builder(), platform, args.build_dir,
                            sim=isinstance(platform, CXXRTLPlatform))
        mainram_size  = litedram_core.size
    else:
        litedram_core = None
        mainram_size  = args.internal_sram_size

    # LiteEth

    if args.with_ethernet:
        if isinstance(platform, CXXRTLPlatform):
            raise NotImplementedError("Ethernet is currently unsupported in simulation.")
        elif isinstance(platform, ArtyA7_35Platform):
            liteeth_config = liteeth.Artix7Config(
                phy_iface = "mii",
                clk_freq  = int(25e6),
            )
        elif isinstance(platform, (ECPIX545Platform, ECPIX585Platform)):
            liteeth_config = liteeth.ECP5Config(
                phy_iface = "rgmii",
                clk_freq  = int(125e6),
            )
        else:
            assert False

        liteeth_pins = request_bare(platform, f"eth_{liteeth_config.phy_iface}", 0)
        liteeth_core = liteeth.Core(liteeth_config, pins=liteeth_pins)
        liteeth_core.build(liteeth.Builder(), platform, args.build_dir)
    else:
        liteeth_core = None

    # UART

    if isinstance(platform, CXXRTLPlatform):
        uart_core = AsyncSerial_Blackbox(
            data_bits = 8,
            divisor   = 1,
        )
    else:
        uart_core = AsyncSerial(
            data_bits = 8,
            divisor   = int(args.sync_clk_freq * 1e6 // args.baudrate),
            pins      = platform.request("uart", 0),
        )

    # SoC and BIOS

    if isinstance(platform, CXXRTLPlatform):
        sync_clk_freq = platform.default_clk_frequency
    else:
        sync_clk_freq = int(args.sync_clk_freq * 1e6)

    soc = MinervaSoC(
        sync_clk_freq = sync_clk_freq,

        cpu_core = MinervaCPU(
            reset_address = 0x00000000,
            with_icache   = True,
            icache_nlines = 16,
            icache_nwords = 4,
            icache_nways  = 1,
            icache_base   = 0x40000000,
            icache_limit  = 0x40000000 + mainram_size,
            with_dcache   = True,
            dcache_nlines = 16,
            dcache_nwords = 4,
            dcache_nways  = 1,
            dcache_base   = 0x40000000,
            dcache_limit  = 0x40000000 + mainram_size,
            with_muldiv   = True,
        ),

        bootrom_addr    = 0x00000000,
        bootrom_size    = 0x8000,
        scratchpad_addr = 0x00008000,
        scratchpad_size = 0x1000,

        uart_addr       = 0x80000000,
        uart_core       = uart_core,
        uart_irqno      = 1,
        timer_addr      = 0x80001000,
        timer_width     = 32,
        timer_irqno     = 0,
    )

    if args.with_sdram:
        soc.add_sdram(litedram_core, addr=0x40000000, cache_size=4096)
    else:
        soc.add_internal_sram(addr=0x40000000, size=args.internal_sram_size)

    if args.with_ethernet:
        soc.add_ethmac(liteeth_core, addr=0x90000000, irqno=2,
                       local_ip=args.local_ip, remote_ip=args.remote_ip)

    soc.build(build_dir=args.build_dir, do_init=True)

    if isinstance(platform, CXXRTLPlatform):
        platform.build(soc, build_dir=args.build_dir, blackboxes={
            "lambdasoc.sim.blackboxes.serial": "serial_pty",
        })
    else:
        platform.build(soc, build_dir=args.build_dir, do_program=True)
