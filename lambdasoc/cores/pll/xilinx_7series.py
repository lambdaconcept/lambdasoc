from collections import namedtuple, OrderedDict

from amaranth import *


__all__ = ["PLL_Xilinx7Series"]


class PLL_Xilinx7Series(Elaboratable):
    class Parameters:
        class Output(namedtuple("Output", ["domain", "freq", "div", "phase"])):
            """PLL output parameters."""
            __slots__ = ()

        """PLL parameters for Xilinx 7 Series FPGAs.

        Parameters
        ----------
        i_domain : str
            Input clock domain.
        i_freq : int or float
            Input clock frequency, in Hz.
        i_reset_less : bool
            If `True`, the input clock domain does not use a reset signal. Defaults to `True`.
        o_domain : str
            Primary output clock domain.
        o_freq : int or float
            Primary output clock frequency, in Hz.

        Attributes
        ----------
        i_domain : str
            Input clock domain.
        i_freq : int
            Input clock frequency, in Hz.
        i_reset_less : bool
            If `True`, the input clock domain does not use a reset signal.
        o_domain : str
            Primary output clock domain.
        o_freq : int
            Primary output clock frequency, in Hz.
        divclk_div : int
            Input clock divisor.
        clkfbout_mult : int
            Feedback clock multiplier.
        clkout0 : :class:`PLL_Xilinx7Series.Parameters.Output`
            Primary output parameters.
        clkout{1..5} : :class:`PLL_Xilinx7Series.Parameters.Output` or None
            Secondary output parameters, or `None` if absent.
        """
        def __init__(self, *, i_domain, i_freq, o_domain, o_freq, i_reset_less=True):
            if not isinstance(i_domain, str):
                raise TypeError("Input domain must be a string, not {!r}"
                                .format(i_domain))
            if not isinstance(i_freq, (int, float)):
                raise TypeError("Input frequency must be an integer or a float, not {!r}"
                                .format(i_freq))
            if not 19e6 <= i_freq <= 800e6:
                raise ValueError("Input frequency must be between 19 and 800 MHz, not {} MHz"
                                 .format(i_freq / 1e6))
            if not isinstance(o_domain, str):
                raise TypeError("Output domain must be a string, not {!r}"
                                .format(o_domain))
            if not isinstance(o_freq, (int, float)):
                raise TypeError("Output frequency must be an integer or a float, not {!r}"
                                 .format(o_freq))
            if not 6.25e6 <= o_freq <= 800e6:
                raise ValueError("Output frequency must be between 6.25 and 800 MHz, not {} MHz"
                                 .format(o_freq / 1e6))

            self.i_domain       = i_domain
            self.i_freq         = int(i_freq)
            self.i_reset_less   = bool(i_reset_less)
            self.o_domain       = o_domain
            self.o_freq         = int(o_freq)

            self._divclk_div    = None
            self._clkfbout_mult = None
            self._clkout0       = None
            self._clkout1       = None
            self._clkout2       = None
            self._clkout3       = None
            self._clkout4       = None
            self._clkout5       = None

            self._2nd_outputs   = OrderedDict()
            self._frozen        = False

        @property
        def divclk_div(self):
            self.compute()
            return self._divclk_div

        @property
        def clkfbout_mult(self):
            self.compute()
            return self._clkfbout_mult

        @property
        def clkout0(self):
            self.compute()
            return self._clkout0

        @property
        def clkout1(self):
            self.compute()
            return self._clkout1

        @property
        def clkout2(self):
            self.compute()
            return self._clkout2

        @property
        def clkout3(self):
            self.compute()
            return self._clkout3

        @property
        def clkout4(self):
            self.compute()
            return self._clkout4

        @property
        def clkout5(self):
            self.compute()
            return self._clkout5

        def add_secondary_output(self, *, domain, freq, phase=0.0):
            """Add secondary PLL output.

            Arguments
            ---------
            domain : str
                Output clock domain.
            freq : int
                Output clock frequency.
            phase : int or float
                Output clock phase, in degrees. Optional. Defaults to 0.
            """
            if self._frozen:
                raise ValueError("PLL parameters have already been computed. Other outputs cannot "
                                 "be added")
            if not isinstance(domain, str):
                raise TypeError("Output domain must be a string, not {!r}"
                                .format(domain))
            if not isinstance(freq, (int, float)):
                raise TypeError("Output frequency must be an integer or a float, not {!r}"
                                .format(freq))
            if not 6.25e6 <= freq <= 800e6:
                raise ValueError("Output frequency must be between 6.25 and 800 MHz, not {} MHz"
                                 .format(freq / 1e6))
            if not isinstance(phase, (int, float)):
                raise TypeError("Output phase must be an integer or a float, not {!r}"
                                .format(phase))
            if not 0 <= phase <= 360.0:
                raise ValueError("Output phase must be between 0 and 360 degrees, not {}"
                                 .format(phase))
            if len(self._2nd_outputs) == 5:
                raise ValueError("This PLL can drive at most 5 secondary outputs")
            if domain in self._2nd_outputs:
                raise ValueError("Output domain '{}' has already been added".format(domain))

            self._2nd_outputs[domain] = freq, phase

        def _iter_variants(self):
            # FIXME: PFD freq ?
            for divclk_div in range(1, 56 + 1):
                for clkfbout_mult in reversed(range(2, 64 + 1)):
                    vco_freq = self.i_freq * clkfbout_mult / divclk_div
                    # This VCO range assumes a -1 speedgrade.
                    if not 800e6 <= vco_freq <= 1600e6:
                        continue
                    for clkout0_div in range(1, 128 + 1):
                        clkout0_freq = vco_freq / clkout0_div
                        if not 6.25e6 <= clkout0_freq <= 800e6:
                            continue
                        yield (divclk_div, clkfbout_mult, clkout0_freq, clkout0_div)

        def compute(self):
            """Compute PLL parameters.

            This method is idempotent. As a side-effect of its first call, the visible state of the
            :class:`PLL_Xilinx7Series.Parameters` instance becomes immutable (e.g. adding more PLL outputs
            will fail).
            """
            if self._frozen:
                return

            variants = list(self._iter_variants())
            if not variants:
                raise ValueError("Input ({} MHz) to primary output ({} MHz) constraint was not "
                                 "satisfied"
                                 .format(self.i_freq / 1e6, self.o_freq / 1e6))

            def error(variant):
                divclk_div, clkfbout_mult, clkout0_freq, clkout0_div = variant
                vco_freq = self.i_freq * clkfbout_mult / divclk_div
                # Idem, assuming a -1 speedgrade.
                return abs(clkout0_freq - self.o_freq), abs(vco_freq - (800e6 + 1600e6) / 2)

            divclk_div, clkfbout_mult, clkout0_freq, clkout0_div = min(variants, key=error)

            self._divclk_div    = divclk_div
            self._clkfbout_mult = clkfbout_mult

            vco_freq = self.i_freq * clkfbout_mult / divclk_div
            self._clkout0 = PLL_Xilinx7Series.Parameters.Output(
                domain = self.o_domain,
                freq   = clkout0_freq,
                div    = clkout0_div,
                phase  = 0.0,
            )

            for i, (out_domain, (out_freq, out_phase)) in enumerate(self._2nd_outputs.items()):
                out_name = "_clkout{}".format(i + 1)
                out_params = PLL_Xilinx7Series.Parameters.Output(
                    domain = out_domain,
                    freq   = out_freq,
                    div    = vco_freq / out_freq,
                    phase  = (self._clkout0.phase + out_phase) % 360.0,
                )
                setattr(self, out_name, out_params)

            self._frozen = True

    """PLL for Xilinx 7 Series FPGAs.

    Parameters
    ----------
    params : :class:`PLL_Xilinx7Series.Parameters`
        PLL parameters.

    Attributes
    ----------
    params : :class:`PLL_Xilinx7Series.Parameters`
        PLL parameters.
    locked : Signal(), out
        PLL lock status.
    """
    def __init__(self, params):
        if not isinstance(params, PLL_Xilinx7Series.Parameters):
            raise TypeError("PLL parameters must be an instance of PLL_Xilinx7Series.Parameters, not {!r}"
                            .format(params))

        params.compute()
        self.params = params
        self.locked = Signal()

    def elaborate(self, platform):
        pll_fb = Signal()

        pll_kwargs = {
            "p_STARTUP_WAIT"   : "FALSE",
            "i_PWRDWN"         : Const(0),
            "o_LOCKED"         : self.locked,

            "p_REF_JITTER1"    : 0.01,
            "p_CLKIN1_PERIOD"  : 1e9 / self.params.i_freq,
            "i_CLKIN1"         : ClockSignal(self.params.i_domain),

            "p_DIVCLK_DIVIDE"  : self.params.divclk_div,
            "p_CLKFBOUT_MULT"  : self.params.clkfbout_mult,
            "i_CLKFBIN"        : pll_fb,
            "o_CLKFBOUT"       : pll_fb,

            "p_CLKOUT0_DIVIDE" : self.params.clkout0.div,
            "p_CLKOUT0_PHASE"  : self.params.clkout0.phase,
            "o_CLKOUT0"        : ClockSignal(self.params.clkout0.domain),
        }

        if self.params.i_reset_less:
            pll_kwargs.update({
                "i_RST" : Const(0),
            })
        else:
            pll_kwargs.update({
                "i_RST" : ResetSignal(self.params.i_domain),
            })

        for i in range(5):
            clkout_name   = "clkout{}".format(i + 1)
            clkout_params = getattr(self.params, clkout_name)
            if clkout_params is not None:
                pll_kwargs.update({
                    f"p_{clkout_name.upper()}_DIVIDE" : clkout_params.div,
                    f"p_{clkout_name.upper()}_PHASE"  : clkout_params.phase,
                    f"o_{clkout_name.upper()}"        : ClockSignal(clkout_params.domain),
                })

        return Instance("PLLE2_BASE", **pll_kwargs)
