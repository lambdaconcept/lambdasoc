# amaranth: UnusedElaboratable=no

import unittest

from amaranth_soc.memory import MemoryMap
from amaranth_boards.ecpix5 import ECPIX585Platform

from litedram.modules import SDRAMModule

from ..cores import litedram


class DummyConfig(litedram.Config):
    phy_name = "dummy"


class ConfigTestCase(unittest.TestCase):
    def test_simple(self):
        cfg = DummyConfig(
            memtype          = "DDR3",
            module_name      = "MT41K256M16",
            module_bytes     =  2,
            module_ranks     =  1,
            input_clk_freq   = int(100e6),
            user_clk_freq    = int(70e6),
            input_domain     = "input",
            user_domain      = "user",
            user_data_width  = 32,
            cmd_buffer_depth =  8,
            csr_data_width   = 32,
        )
        self.assertEqual(cfg.memtype, "DDR3")
        self.assertEqual(cfg.module_name, "MT41K256M16")
        self.assertEqual(cfg.module_bytes, 2)
        self.assertEqual(cfg.module_ranks, 1)
        self.assertEqual(cfg.phy_name, "dummy")
        self.assertEqual(cfg.input_clk_freq, int(100e6))
        self.assertEqual(cfg.user_clk_freq, int(70e6))
        self.assertEqual(cfg.input_domain, "input")
        self.assertEqual(cfg.user_domain, "user")
        self.assertEqual(cfg.user_data_width, 32)
        self.assertEqual(cfg.cmd_buffer_depth, 8)
        self.assertEqual(cfg.csr_data_width, 32)

    def test_get_module(self):
        cfg = DummyConfig(
            memtype        = "DDR3",
            module_name    = "MT41K256M16",
            module_bytes   = 2,
            module_ranks   = 1,
            input_clk_freq = int(100e6),
            user_clk_freq  = int(70e6),
        )
        module = cfg.get_module()
        self.assertIsInstance(module, SDRAMModule)

    def test_wrong_memtype(self):
        with self.assertRaisesRegex(ValueError,
                r"Unsupported DRAM type, must be one of \"SDR\", \"DDR\", \"LPDDR\", \"DDR2\", "
                r"\"DDR3\" or \"DDR4\", not 'foo'"):
            cfg = DummyConfig(
                memtype        = "foo",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
            )

    def test_wrong_module_name(self):
        with self.assertRaisesRegex(ValueError,
                r"Module name must be a string, not 42"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = 42,
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
            )

    def test_wrong_module_bytes(self):
        with self.assertRaisesRegex(ValueError,
                r"Number of byte groups must be a positive integer, not 'foo'"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = "foo",
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
            )

    def test_wrong_module_ranks(self):
        with self.assertRaisesRegex(ValueError,
                r"Number of ranks must be a positive integer, not 'foo'"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = "foo",
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
            )

    def test_wrong_input_clk_freq(self):
        with self.assertRaisesRegex(ValueError,
                r"Input clock frequency must be a positive integer, not -1"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = -1,
                user_clk_freq  = int(70e6),
            )

    def test_wrong_user_clk_freq(self):
        with self.assertRaisesRegex(ValueError,
                r"User clock frequency must be a positive integer, not -1"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = -1,
            )

    def test_wrong_input_domain(self):
        with self.assertRaisesRegex(ValueError,
                r"Input domain name must be a string, not 42"):
            cfg = DummyConfig(
                memtype         = "DDR3",
                module_name     = "MT41K256M16",
                module_bytes    = 2,
                module_ranks    = 1,
                input_clk_freq  = int(100e6),
                user_clk_freq   = int(70e6),
                input_domain    = 42,
            )

    def test_wrong_user_domain(self):
        with self.assertRaisesRegex(ValueError,
                r"User domain name must be a string, not 42"):
            cfg = DummyConfig(
                memtype         = "DDR3",
                module_name     = "MT41K256M16",
                module_bytes    = 2,
                module_ranks    = 1,
                input_clk_freq  = int(100e6),
                user_clk_freq   = int(70e6),
                user_domain    = 42,
            )

    def test_wrong_user_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"User port data width must be one of 8, 16, 32, 64 or 128, not 42"):
            cfg = DummyConfig(
                memtype         = "DDR3",
                module_name     = "MT41K256M16",
                module_bytes    = 2,
                module_ranks    = 1,
                input_clk_freq  = int(100e6),
                user_clk_freq   = int(70e6),
                user_data_width = 42,
            )

    def test_wrong_cmd_buffer_depth(self):
        with self.assertRaisesRegex(ValueError,
                r"Command buffer depth must be a positive integer, not 'foo'"):
            cfg = DummyConfig(
                memtype          = "DDR3",
                module_name      = "MT41K256M16",
                module_bytes     = 2,
                module_ranks     = 1,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(70e6),
                cmd_buffer_depth = "foo",
            )

    def test_wrong_csr_data_width(self):
        with self.assertRaisesRegex(ValueError,
                r"CSR data width must be one of 8, 16, 32, or 64, not 42"):
            cfg = DummyConfig(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
                csr_data_width = 42,
            )


class ECP5ConfigTestCase(unittest.TestCase):
    def test_simple(self):
        cfg = litedram.ECP5Config(
            memtype        = "DDR3",
            module_name    = "MT41K256M16",
            module_bytes   = 2,
            module_ranks   = 1,
            input_clk_freq = int(100e6),
            user_clk_freq  = int(70e6),
            init_clk_freq  = int(25e6),
        )
        self.assertEqual(cfg.init_clk_freq, int(25e6))
        self.assertEqual(cfg.phy_name, "ECP5DDRPHY")

    def test_wrong_init_clk_freq(self):
        with self.assertRaisesRegex(ValueError,
                r"Init clock frequency must be a positive integer, not -1"):
            cfg = litedram.ECP5Config(
                memtype        = "DDR3",
                module_name    = "MT41K256M16",
                module_bytes   = 2,
                module_ranks   = 1,
                input_clk_freq = int(100e6),
                user_clk_freq  = int(70e6),
                init_clk_freq  = -1,
            )


class Artix7ConfigTestCase(unittest.TestCase):
    def test_simple(self):
        cfg = litedram.Artix7Config(
            memtype          = "DDR3",
            speedgrade       = "-1",
            cmd_latency      = 0,
            module_name      = "MT41K128M16",
            module_bytes     = 2,
            module_ranks     = 1,
            rtt_nom          = 60,
            rtt_wr           = 60,
            ron              = 34,
            input_clk_freq   = int(100e6),
            user_clk_freq    = int(100e6),
            iodelay_clk_freq = int(200e6),
        )
        self.assertEqual(cfg.speedgrade, "-1")
        self.assertEqual(cfg.cmd_latency, 0)
        self.assertEqual(cfg.rtt_nom, 60)
        self.assertEqual(cfg.rtt_wr, 60)
        self.assertEqual(cfg.ron, 34)
        self.assertEqual(cfg.iodelay_clk_freq, int(200e6))
        self.assertEqual(cfg.phy_name, "A7DDRPHY")

    def test_wrong_speedgrade(self):
        with self.assertRaisesRegex(ValueError,
                r"Speed grade must be one of '-1', '-2', '-2L', '-2G', '-3', "
                r"not '-42'"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-42",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = 60,
                ron              = 34,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = int(200e6),
            )

    def test_wrong_cmd_latency(self):
        with self.assertRaisesRegex(ValueError,
                r"Command latency must be a non-negative integer, not -42"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = -42,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = 60,
                ron              = 34,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = int(200e6),
            )

    def test_wrong_rtt_nom(self):
        with self.assertRaisesRegex(ValueError,
                r"Nominal termination impedance must be a non-negative integer, not -42"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = -42,
                rtt_wr           = 60,
                ron              = 34,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = int(200e6),
            )

    def test_wrong_rtt_wr(self):
        with self.assertRaisesRegex(ValueError,
                r"Write termination impedance must be a non-negative integer, not -42"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = -42,
                ron              = 34,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = int(200e6),
            )

    def test_wrong_ron(self):
        with self.assertRaisesRegex(ValueError,
                r"Output driver impedance must be a non-negative integer, not -42"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = 60,
                ron              = -42,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = int(200e6),
            )

    def test_wrong_iodelay_clk_freq(self):
        with self.assertRaisesRegex(ValueError,
                r"IODELAY clock frequency must be a positive integer, not -1"):
            cfg = litedram.Artix7Config(
                memtype          = "DDR3",
                speedgrade       = "-1",
                cmd_latency      = 0,
                module_name      = "MT41K128M16",
                module_bytes     = 2,
                module_ranks     = 1,
                rtt_nom          = 60,
                rtt_wr           = 60,
                ron              = 34,
                input_clk_freq   = int(100e6),
                user_clk_freq    = int(100e6),
                iodelay_clk_freq = -1,
            )


class NativePortTestCase(unittest.TestCase):
    def test_simple(self):
        port = litedram.NativePort(addr_width=10, data_width=32)
        self.assertEqual(port.addr_width, 10)
        self.assertEqual(port.data_width, 32)
        self.assertEqual(port.granularity, 8)
        self.assertEqual(len(port.cmd.addr), 10)
        self.assertEqual(len(port.w.data), 32)
        self.assertEqual(len(port.w.we), 4)
        self.assertEqual(len(port.r.data), 32)
        self.assertEqual(
            repr(port),
            "(rec port "
              "(rec port__cmd valid ready last we addr) "
              "(rec port__w valid ready data we) "
              "(rec port__r valid ready data))"
        )

    def test_memory_map(self):
        port = litedram.NativePort(addr_width=10, data_width=32)
        port_map = MemoryMap(addr_width=12, data_width=8)
        port.memory_map = port_map
        self.assertIs(port.memory_map, port_map)

    def test_wrong_memory_map(self):
        port = litedram.NativePort(addr_width=10, data_width=32)
        with self.assertRaisesRegex(TypeError,
                r"Memory map must be an instance of MemoryMap, not 'foo'"):
            port.memory_map = "foo"

    def test_wrong_memory_map_data_width(self):
        port = litedram.NativePort(addr_width=10, data_width=32)
        port_map = MemoryMap(addr_width=11, data_width=16)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has data width 16, which is not the same as native port granularity "
                r"8"):
            port.memory_map = port_map

    def test_wrong_memory_map_addr_width(self):
        port = litedram.NativePort(addr_width=10, data_width=32)
        port_map = MemoryMap(addr_width=11, data_width=8)
        with self.assertRaisesRegex(ValueError,
                r"Memory map has address width 11, which is not the same as native port address "
                r"width 12 \(10 address bits \+ 2 granularity bits\)"):
            port.memory_map = port_map


class CoreTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cfg = litedram.ECP5Config(
            memtype        = "DDR3",
            module_name    = "MT41K256M16",
            module_bytes   = 2,
            module_ranks   = 1,
            input_clk_freq = int(100e6),
            user_clk_freq  = int(70e6),
            init_clk_freq  = int(25e6),
        )

    def test_simple(self):
        core = litedram.Core(self._cfg)
        self.assertIs(core.config, self._cfg)
        self.assertEqual(core.name, "core")
        self.assertEqual(core.size, 512 * 1024 * 1024)
        self.assertEqual(core.user_port.addr_width, 25)
        self.assertEqual(core.user_port.data_width, 128)
        self.assertEqual(core.user_port.memory_map.addr_width, 29)
        self.assertEqual(core.user_port.memory_map.data_width, 8)

    def test_ctrl_bus_not_ready(self):
        core = litedram.Core(self._cfg)
        with self.assertRaisesRegex(AttributeError,
                r"Control bus memory map has not been populated. Core.build\(do_build=True\) must "
                r"be called before accessing Core\.ctrl_bus"):
            core.ctrl_bus

    def test_wrong_config(self):
        with self.assertRaisesRegex(TypeError,
                r"Config must be an instance of litedram\.Config, not 'foo'"):
            core = litedram.Core("foo")

    def test_wrong_name(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 42"):
            core = litedram.Core(self._cfg, name=42)


class BuilderTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cfg = litedram.ECP5Config(
            memtype        = "DDR3",
            module_name    = "MT41K256M16",
            module_bytes   = 2,
            module_ranks   = 1,
            input_clk_freq = int(100e6),
            user_clk_freq  = int(70e6),
            init_clk_freq  = int(25e6),
        )

    def test_prepare(self):
        core = litedram.Core(self._cfg)
        builder = litedram.Builder()
        builder.prepare(core, ECPIX585Platform())
        self.assertEqual(list(builder.namespace), ["core"])

    def test_prepare_name_conflict(self):
        core = litedram.Core(self._cfg)
        builder = litedram.Builder()
        builder.prepare(core, ECPIX585Platform())
        with self.assertRaisesRegex(ValueError,
                r"LiteDRAM core name 'core' has already been used for a previous build\. Building "
                r"this instance may overwrite previous build products\. Passing `name_force=True` "
                r"will disable this check"):
            builder.prepare(core, ECPIX585Platform())

    def test_prepare_name_force(self):
        core = litedram.Core(self._cfg)
        builder = litedram.Builder()
        builder.prepare(core, ECPIX585Platform())
        builder.prepare(core, ECPIX585Platform(), name_force=True)

    def test_prepare_wrong_core(self):
        builder = litedram.Builder()
        with self.assertRaisesRegex(TypeError,
                r"LiteDRAM core must be an instance of litedram.Core, not 'foo'"):
            builder.prepare("foo", ECPIX585Platform())

    def test_prepare_wrong_platform(self):
        core = litedram.Core(self._cfg)
        builder = litedram.Builder()
        with self.assertRaisesRegex(TypeError,
                r"Target platform must be an instance of amaranth.build.plat.Platform, not 'foo'"):
            builder.prepare(core, "foo")
