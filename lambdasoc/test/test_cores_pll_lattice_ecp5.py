# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *

from ..cores.pll.lattice_ecp5 import PLL_LatticeECP5


class PLL_LatticeECP5__ParametersTestCase(unittest.TestCase):
    def test_simple(self):
        params1 = PLL_LatticeECP5.Parameters(
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
        self.assertEqual(params1.fb_internal, False)

        params2 = PLL_LatticeECP5.Parameters(
            i_domain     = "baz",
            i_freq       = int(12e6),
            i_reset_less = False,
            o_domain     = "qux",
            o_freq       = int(48e6),
            fb_internal  = True,
        )
        self.assertEqual(params2.i_domain, "baz")
        self.assertEqual(params2.i_freq, 12e6)
        self.assertEqual(params2.i_reset_less, False)
        self.assertEqual(params2.o_domain, "qux")
        self.assertEqual(params2.o_freq, 48e6)
        self.assertEqual(params2.fb_internal, True)

    def test_wrong_i_domain(self):
        with self.assertRaisesRegex(TypeError,
                r"Input domain must be a string, not 1"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = 1,
                i_freq   = 100e6,
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_i_freq_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Input frequency must be an integer or a float, not 'baz'"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "foo",
                i_freq   = "baz",
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_i_freq_range(self):
        with self.assertRaisesRegex(ValueError,
                r"Input frequency must be between 8 and 400 MHz, not 420.0 MHz"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "foo",
                i_freq   = 420e6,
                o_domain = "bar",
                o_freq   = 50e6,
            )

    def test_wrong_o_domain(self):
        with self.assertRaisesRegex(TypeError,
                r"Output domain must be a string, not 1"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "foo",
                i_freq   = 100e6,
                o_domain = 1,
                o_freq   = 50e6,
            )

    def test_wrong_o_freq_type(self):
        with self.assertRaisesRegex(TypeError,
                r"Output frequency must be an integer or a float, not 'baz'"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "foo",
                i_freq   = 50e6,
                o_domain = "bar",
                o_freq   = "baz",
            )

    def test_wrong_o_freq_range(self):
        with self.assertRaisesRegex(ValueError,
                r"Output frequency must be between 10 and 400 MHz, not 420.0 MHz"):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "foo",
                i_freq   = 100e6,
                o_domain = "bar",
                o_freq   = 420e6,
            )

    def test_add_secondary_output_wrong_domain(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output domain must be a string, not 1"):
            params.add_secondary_output(domain=1, freq=10e6)

    def test_add_secondary_output_wrong_freq_type(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output frequency must be an integer or a float, not 'a'"):
            params.add_secondary_output(domain="baz", freq="a")

    def test_add_secondary_output_wrong_freq_range(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(ValueError,
                r"Output frequency must be between 10 and 400 MHz, not 8.0 MHz"):
            params.add_secondary_output(domain="baz", freq=8e6)

    def test_add_secondary_output_wrong_phase_type(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(TypeError,
                r"Output phase must be an integer or a float, not 'a'"):
            params.add_secondary_output(domain="baz", freq=10e6, phase="a")

    def test_add_secondary_output_wrong_phase_range(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        with self.assertRaisesRegex(ValueError,
                r"Output phase must be between 0 and 360 degrees, not -1"):
            params.add_secondary_output(domain="baz", freq=10e6, phase=-1)

    def test_add_secondary_output_exceeded(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.add_secondary_output(domain="a", freq=10e6)
        params.add_secondary_output(domain="b", freq=10e6)
        params.add_secondary_output(domain="c", freq=10e6)
        with self.assertRaisesRegex(ValueError,
                r"This PLL can drive at most 3 secondary outputs"):
            params.add_secondary_output(domain="d", freq=10e6)

    def test_add_secondary_output_same_domain(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.add_secondary_output(domain="a", freq=10e6)
        with self.assertRaisesRegex(ValueError,
                r"Output domain 'a' has already been added"):
            params.add_secondary_output(domain="a", freq=10e6)

    def test_compute_primary(self):
        def result(i_freq, o_freq):
            params = PLL_LatticeECP5.Parameters(
                i_domain = "i",
                i_freq   = i_freq,
                o_domain = "o",
                o_freq   = o_freq,
            )
            params.compute()
            return (params.i_div, params.fb_div, params.op.div)

        vectors = [
            # Values are taken from ecppll in prjtrellis.
            # i_freq, o_freq, i_div, fb_div, op_div
            (   12e6,   48e6,     1,      4,     12),
            (   12e6,   60e6,     1,      5,     10),
            (   20e6,   30e6,     2,      3,     20),
            (   45e6,   30e6,     3,      2,     20),
            (  100e6,  400e6,     1,      4,      1),
            (  200e6,  400e6,     1,      2,      1),
            (   50e6,  400e6,     1,      8,      1),
            (   70e6,   40e6,     7,      4,     15),
            (   12e6,   36e6,     1,      3,     17),
            (   12e6,   96e6,     1,      8,      6),
            (   90e6,   40e6,     9,      4,     15),
            (   90e6,   50e6,     9,      5,     12),
            (   43e6,   86e6,     1,      2,      7),
        ]

        self.assertEqual(
            [(i_freq, o_freq, *result(i_freq, o_freq)) for i_freq, o_freq, *_ in vectors],
            vectors
        )

    # TODO
    # def test_compute_secondary(self):
        # pass

    def test_add_secondary_output_frozen(self):
        params = PLL_LatticeECP5.Parameters(
            i_domain = "foo",
            i_freq   = 100e6,
            o_domain = "bar",
            o_freq   = 50e6,
        )
        params.compute()
        with self.assertRaisesRegex(ValueError,
                r"PLL parameters have already been computed. Other outputs cannot be added"):
            params.add_secondary_output(domain="a", freq=10e6)
