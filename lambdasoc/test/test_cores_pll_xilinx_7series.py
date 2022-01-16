# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *

from ..cores.pll.xilinx_7series import PLL_Xilinx7Series


class PLL_Xilinx7Series__ParametersTestCase(unittest.TestCase):
    def test_simple(self):
        params1 = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        self.assertEqual(params1.i_domain, "foo")
        self.assertEqual(params1.i_freq, 100e6)
        self.assertEqual(params1.i_reset_less, True)
        self.assertEqual(params1.o_domain, "bar")
        self.assertEqual(params1.o_freq, 50e6)

        params2 = PLL_Xilinx7Series.Parameters(
            i_domain     = "baz",
            i_freq       = int(20e6),
            i_reset_less = False,
            o_domain     = "qux",
            o_freq       = int(40e6),
        )
        self.assertEqual(params2.i_domain, "baz")
        self.assertEqual(params2.i_freq, 20e6)
        self.assertEqual(params2.i_reset_less, False)
        self.assertEqual(params2.o_domain, "qux")
        self.assertEqual(params2.o_freq, 40e6)

    def test_wrong_i_domain(self):
        with self.assertRaisesRegex(TypeError,
                r"Input domain must be a string, not 1"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = 1,
                i_freq   = 100e6,
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_i_freq_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Input frequency must be an integer or a float, not 'baz'"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = "foo",
                i_freq   = "baz",
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_i_freq_range(self):
        with self.assertRaisesRegex(ValueError,
                r"Input frequency must be between 19 and 800 MHz, not 820.0 MHz"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = "foo",
                i_freq   = 820e6,
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_o_domain(self):
        with self.assertRaisesRegex(TypeError,
                r"Output domain must be a string, not 1"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = "foo",
                i_freq   = 100e6,
                o_domain = 1,
                o_freq   = 50e6,
            )

    def test_wrong_o_freq_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Output frequency must be an integer or a float, not 'baz'"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = "foo",
                i_freq   = 50e6,
                o_domain = "bar",
                o_freq   = "baz",
            )

    def test_wrong_o_freq_range(self):
        with self.assertRaisesRegex(ValueError,
                r"Output frequency must be between 6.25 and 800 MHz, not 820.0 MHz"):
            params = PLL_Xilinx7Series.Parameters(
                i_domain = "foo",
                i_freq   = 100e6,
                o_domain = "bar",
                o_freq   = 820e6,
            )

    def test_add_secondary_output_wrong_domain(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output domain must be a string, not 1"):
            params.add_secondary_output(domain=1, freq=10e6)

    def test_add_secondary_output_wrong_freq_type(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output frequency must be an integer or a float, not 'a'"):
            params.add_secondary_output(domain="baz", freq="a")

    def test_add_secondary_output_wrong_freq_range(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(ValueError,
                r"Output frequency must be between 6.25 and 800 MHz, not 5.0 MHz"):
            params.add_secondary_output(domain="baz", freq=5e6)

    def test_add_secondary_output_wrong_phase_type(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output phase must be an integer or a float, not 'a'"):
            params.add_secondary_output(domain="baz", freq=10e6, phase="a")

    def test_add_secondary_output_wrong_phase_range(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(ValueError,
                r"Output phase must be between 0 and 360 degrees, not -1"):
            params.add_secondary_output(domain="baz", freq=10e6, phase=-1)

    def test_add_secondary_output_exceeded(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.add_secondary_output(domain="a", freq=10e6)
        params.add_secondary_output(domain="b", freq=10e6)
        params.add_secondary_output(domain="c", freq=10e6)
        params.add_secondary_output(domain="d", freq=10e6)
        params.add_secondary_output(domain="e", freq=10e6)
        with self.assertRaisesRegex(ValueError,
                r"This PLL can drive at most 5 secondary outputs"):
            params.add_secondary_output(domain="f", freq=10e6)

    def test_add_secondary_output_same_domain(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.add_secondary_output(domain="a", freq=10e6)
        with self.assertRaisesRegex(ValueError,
                r"Output domain 'a' has already been added"):
            params.add_secondary_output(domain="a", freq=10e6)

    # TODO
    # def test_compute_primary(self):
    #     pass

    # TODO
    # def test_compute_secondary(self):
        # pass

    def test_add_secondary_output_frozen(self):
        params = PLL_Xilinx7Series.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.compute()
        with self.assertRaisesRegex(ValueError,
                r"PLL parameters have already been computed. Other outputs cannot be added"):
            params.add_secondary_output(domain="a", freq=10e6)
