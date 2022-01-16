from abc import ABCMeta, abstractmethod
import csv
import jinja2
import textwrap
import re

from amaranth import *
from amaranth import tracer
from amaranth.utils import log2_int
from amaranth.hdl.rec import Layout
from amaranth.build.plat import Platform
from amaranth.build.run import BuildPlan, BuildProducts

from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap

from .. import __version__
from ..periph import IRQLine


__all__ = [
    "Config", "ECP5Config", "Artix7Config",
    "Core",
    "Builder",
]

class Config(metaclass=ABCMeta):
    def __init__(self, *,
            phy_iface,
            clk_freq,
            rx_slots = 2,
            tx_slots = 2,
            endianess="little"):

        if phy_iface not in {"mii", "rmii", "rgmii"}:
            raise ValueError("LiteEth PHY interface must be one of \"mii\", \"rmii\" or "
                             "\"rgmii\", not {!r}".format(phy_iface))
        if not isinstance(clk_freq, int) or clk_freq <= 0:
            raise ValueError("LiteEth clock frequency must be a positive integer, not {!r}"
                             .format(clk_freq))
        if not isinstance(rx_slots, int) or rx_slots < 0:
            raise ValueError("LiteEth Rx FIFO slots must be a non-negative integer, not {!r}"
                             .format(rx_slots))
        if not isinstance(tx_slots, int) or tx_slots < 0:
            raise ValueError("LiteEth Tx FIFO slots must be a non-negative integer, not {!r}"
                             .format(tx_slots))
        if endianess not in {"big", "little"}:
            raise ValueError("LitEth endianess must be one of \"big\" or \"little\", not {!r}"
                             .format(endianess))

        self.phy_iface = phy_iface
        self.clk_freq  = clk_freq
        self.rx_slots  = rx_slots
        self.tx_slots  = tx_slots
        self.endianess = endianess
        # FIXME: hardcoded
        self.ctrl_addr = 0x0
        self.data_addr = 0x10000

    @property
    @abstractmethod
    def phy_name(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def vendor(self):
        raise NotImplementedError


class ECP5Config(Config):
    vendor = "lattice"

    @property
    def phy_name(self):
        if self.phy_iface in {"mii", "rmii", "gmii"}:
            return "LiteEthPHY{}".format(self.phy_iface.upper())
        elif self.phy_iface == "rgmii":
            return "LiteEthECP5PHYRGMII"
        else:
            assert False


class Artix7Config(Config):
    vendor = "xilinx"

    @property
    def phy_name(self):
        if self.phy_iface in {"mii", "rmii", "gmii"}:
            return "LiteEthPHY{}".format(self.phy_iface.upper())
        elif self.phy_iface == "rgmii":
            return "LiteEthS7PHYRGMII"
        else:
            assert False


class Core(Elaboratable):
    def __init__(self, config, *, pins=None, name=None, src_loc_at=0):
        if not isinstance(config, Config):
            raise TypeError("Config must be an instance liteeth.Config, "
                            "not {!r}"
                            .format(config))
        self.config = config

        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}".format(name))
        self.name = name or tracer.get_var_name(depth=2 + src_loc_at)

        self.irq = IRQLine(name=f"{self.name}_irq")

        self._bus  = None
        self._pins = pins

    @property
    def bus(self):
        if self._bus is None:
            raise AttributeError("Bus memory map has not been populated. "
                                 "Core.build(do_build=True) must be called before accessing "
                                 "Core.bus")
        return self._bus

    def _populate_map(self, build_products):
        if not isinstance(build_products, BuildProducts):
            raise TypeError("Build products must be an instance of BuildProducts, not {!r}"
                            .format(build_products))

        # LiteEth's Wishbone bus has a granularity of 8 bits.
        ctrl_map = MemoryMap(addr_width=1, data_width=8)
        data_map = MemoryMap(addr_width=1, data_width=8)

        csr_csv = build_products.get(f"{self.name}_csr.csv", mode="t")
        for row in csv.reader(csr_csv.split("\n"), delimiter=","):
            if not row or row[0][0] == "#": continue
            res_type, res_name, addr, size, attrs = row
            if res_type == "csr_register":
                ctrl_map.add_resource(
                    object(),
                    name   = res_name,
                    addr   = int(addr, 16),
                    size   = int(size, 10) * 32 // ctrl_map.data_width,
                    extend = True,
                )

        # TODO: rephrase
        # The LiteEth MAC core uses a memory region capable of holding an IEEE 802.3 Ethernet frame
        # (rounded to the nearest power-of-two) for each Rx/Tx slot.
        data_map.add_resource(
            object(),
            name   = "ethmac_slots",
            size   = (self.config.rx_slots + self.config.tx_slots) * 2048,
            extend = True,
        )

        bus_map = MemoryMap(addr_width=1, data_width=8)
        bus_map.add_window(ctrl_map, addr=self.config.ctrl_addr, extend=True)
        bus_map.add_window(data_map, addr=self.config.data_addr, extend=True)

        self._bus = wishbone.Interface(
            addr_width  = bus_map.addr_width
                        - log2_int(32 // bus_map.data_width),
            data_width  = 32,
            granularity = bus_map.data_width,
            features    = {"cti", "bte", "err"},
        )
        self._bus.memory_map = bus_map

    def build(self, builder, platform, build_dir, *, do_build=True, name_force=False):
        if not isinstance(builder, Builder):
            raise TypeError("Builder must be an instance of liteeth.Builder, not {!r}"
                            .format(builder))

        plan = builder.prepare(self, name_force=name_force)
        if not do_build:
            return plan

        products = plan.execute_local(f"{build_dir}/lambdasoc.cores.liteeth") # TODO __package__
        self._populate_map(products)

        core_src = f"liteeth_core/liteeth_core.v"
        platform.add_file(core_src, products.get(core_src, mode="t"))

        return products

    def elaborate(self, platform):
        core_kwargs = {
                "i_sys_clock" : ClockSignal("sync"),
                "i_sys_reset" : ResetSignal("sync"),

                "i_wishbone_adr"   : self.bus.adr,
                "i_wishbone_dat_w" : self.bus.dat_w,
                "o_wishbone_dat_r" : self.bus.dat_r,
                "i_wishbone_sel"   : self.bus.sel,
                "i_wishbone_cyc"   : self.bus.cyc,
                "i_wishbone_stb"   : self.bus.stb,
                "o_wishbone_ack"   : self.bus.ack,
                "i_wishbone_we"    : self.bus.we,
                "i_wishbone_cti"   : self.bus.cti,
                "i_wishbone_bte"   : self.bus.bte,
                "o_wishbone_err"   : self.bus.err,

                "o_interrupt" : self.irq,
        }

        if self._pins is not None:
            if self.config.phy_iface == "mii":
                core_kwargs.update({
                    "i_mii_eth_clocks_tx" : self._pins.tx_clk,
                    "i_mii_eth_clocks_rx" : self._pins.rx_clk,
                    "o_mii_eth_rst_n"     : self._pins.rst,
                    "io_mii_eth_mdio"     : self._pins.mdio,
                    "o_mii_eth_mdc"       : self._pins.mdc,
                    "i_mii_eth_rx_dv"     : self._pins.rx_dv,
                    "i_mii_eth_rx_er"     : self._pins.rx_er,
                    "i_mii_eth_rx_data"   : self._pins.rx_data,
                    "o_mii_eth_tx_en"     : self._pins.tx_en,
                    "o_mii_eth_tx_data"   : self._pins.tx_data,
                    "i_mii_eth_col"       : self._pins.col,
                    "i_mii_eth_crs"       : self._pins.crs,
                })
            elif self.config.phy_iface == "rmii":
                core_kwargs.update({
                    "o_rmii_eth_clocks_ref_clk" : self._pins.clk,
                    "o_rmii_eth_rst_n"          : self._pins.rst,
                    "io_rmii_eth_mdio"          : self._pins.mdio,
                    "o_rmii_eth_mdc"            : self._pins.mdc,
                    "i_rmii_eth_crs_dv"         : self._pins.crs_dv,
                    "i_rmii_eth_rx_data"        : self._pins.rx_data,
                    "o_rmii_eth_tx_en"          : self._pins.tx_en,
                    "o_rmii_eth_tx_data"        : self._pins.tx_data,
                })
            elif self.config.phy_iface == "gmii":
                core_kwargs.update({
                    "o_gmii_eth_clocks_tx" : self._pins.tx_clk,
                    "i_gmii_eth_clocks_rx" : self._pins.rx_clk,
                    "o_gmii_eth_rst_n"     : self._pins.rst,
                    "i_gmii_eth_int_n"     : Const(1),
                    "io_gmii_eth_mdio"     : self._pins.mdio,
                    "o_gmii_eth_mdc"       : self._pins.mdc,
                    "i_gmii_eth_rx_dv"     : self._pins.rx_dv,
                    "i_gmii_eth_rx_er"     : self._pins.rx_er,
                    "i_gmii_eth_rx_data"   : self._pins.rx_data,
                    "o_gmii_eth_tx_en"     : self._pins.tx_en,
                    "o_gmii_eth_tx_er"     : self._pins.tx_er,
                    "o_gmii_eth_tx_data"   : self._pins.tx_data,
                    "i_gmii_eth_col"       : self._pins.col,
                    "i_gmii_eth_crs"       : self._pins.crs,
                })
            elif self.config.phy_iface == "rgmii":
                core_kwargs.update({
                    "o_rgmii_eth_clocks_tx" : self._pins.tx_clk,
                    "i_rgmii_eth_clocks_rx" : self._pins.rx_clk,
                    "o_rgmii_eth_rst_n"     : self._pins.rst,
                    "i_rgmii_eth_int_n"     : Const(1),
                    "io_rgmii_eth_mdio"     : self._pins.mdio,
                    "o_rgmii_eth_mdc"       : self._pins.mdc,
                    "i_rgmii_eth_rx_ctl"    : self._pins.rx_ctrl,
                    "i_rgmii_eth_rx_data"   : self._pins.rx_data,
                    "o_rgmii_eth_tx_ctl"    : self._pins.tx_ctrl,
                    "o_rgmii_eth_tx_data"   : self._pins.tx_data,
                })
            else:
                assert False

        return Instance(f"{self.name}", **core_kwargs)


class Builder:
    file_templates = {
        "build_{{top.name}}.sh": r"""
            # {{autogenerated}}
            set -e
            {{emit_commands()}}
        """,
        "{{top.name}}_config.yml": r"""
            # {{autogenerated}}
            {
                # PHY ----------------------------------------------------------------------
                "phy":         {{top.config.phy_name}},
                "vendor":      {{top.config.vendor}},

                # Core ---------------------------------------------------------------------
                "clk_freq":    {{top.config.clk_freq}},
                "core":        wishbone,
                "nrxslots":    {{top.config.rx_slots}},
                "ntxslots":    {{top.config.tx_slots}},
                "endianness":   {{top.config.endianess}},

                "soc": {
                    "mem_map": {
                        "csr":    {{hex(top.config.ctrl_addr)}},
                        "ethmac": {{hex(top.config.data_addr)}},
                    },
                },
            }
        """,
    }
    command_templates = [
        # FIXME: add --name upstream
        r"""
            python -m liteeth.gen
                --output-dir {{top.name}}
                --gateware-dir {{top.name}}
                --csr-csv {{top.name}}_csr.csv
                {{top.name}}_config.yml
        """,
    ]

    def __init__(self):
        self.namespace = set()

    def prepare(self, core, *, name_force=False):
        if not isinstance(core, Core):
            raise TypeError("LiteEth core must be an instance of liteeth.Core, not {!r}"
                            .format(core))

        if core.name in self.namespace and not name_force:
            raise ValueError(
                "LiteEth core name '{}' has already been used for a previous build. Building "
                "this instance may overwrite previous build products. Passing `name_force=True` "
                "will disable this check".format(core.name)
            )
        self.namespace.add(core.name)

        autogenerated = f"Automatically generated by LambdaSoC {__version__}. Do not edit."

        def emit_commands():
            commands = []
            for index, command_tpl in enumerate(self.command_templates):
                command = render(command_tpl, origin="<command#{}>".format(index + 1))
                command = re.sub(r"\s+", " ", command)
                commands.append(command)
            return "\n".join(commands)

        def render(source, origin):
            try:
                source = textwrap.dedent(source).strip()
                compiled = jinja2.Template(source, trim_blocks=True, lstrip_blocks=True)
            except jinja2.TemplateSyntaxError as e:
                e.args = ("{} (at {}:{})".format(e.message, origin, e.lineno),)
                raise
            return compiled.render({
                "autogenerated": autogenerated,
                "emit_commands": emit_commands,
                "hex": hex,
                "top": core,
            })

        plan = BuildPlan(script=f"build_{core.name}")
        for filename_tpl, content_tpl in self.file_templates.items():
            plan.add_file(render(filename_tpl, origin=filename_tpl),
                          render(content_tpl,  origin=content_tpl))
        return plan
