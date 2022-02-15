from collections import namedtuple, OrderedDict

from amaranth import *


__all__ = ["PLL_LatticeECP5"]


class PLL_LatticeECP5(Elaboratable):
    class Parameters:
        class Output(namedtuple("Output", ["domain", "freq", "div", "cphase", "fphase"])):
            """PLL output parameters."""
            __slots__ = ()

        """PLL parameters for Lattice ECP5 FPGAs.

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
        internal_fb : bool
            Internal feedback mode. Optional. Defaults to `False`.

        Attributes
        ----------
        i_domain : str
            Input clock domain.
        i_freq : int
            Input clock frequency, in Hz.
        i_reset_less : bool
            If `True`, the input clock domain does not use a reset signal.
        i_div : int
            Input clock divisor.
        o_domain : str
            Primary output clock domain.
        o_freq : int
            Primary output clock frequency, in Hz.
        fb_internal : bool
            Internal feedback mode.
        fb_div : int
            Feedback clock divisor.
        op : :class:`PLL_LatticeECP5.Parameters.Output`
            Primary output parameters.
        os, os2, os3 : :class:`PLL_LatticeECP5.Parameters.Output` or None
            Secondary output parameters, or `None` if absent.
        """
        def __init__(self, *, i_domain, i_freq, o_domain, o_freq, i_reset_less=True, fb_internal=False):
            if not isinstance(i_domain, str):
                raise TypeError("Input domain must be a string, not {!r}"
                                .format(i_domain))
            if not isinstance(i_freq, (int, float)):
                raise TypeError("Input frequency must be an integer or a float, not {!r}"
                                .format(i_freq))
            if not 8e6 <= i_freq <= 400e6:
                raise ValueError("Input frequency must be between 8 and 400 MHz, not {} MHz"
                                 .format(i_freq / 1e6))
            if not isinstance(o_domain, str):
                raise TypeError("Output domain must be a string, not {!r}"
                                .format(o_domain))
            if not isinstance(o_freq, (int, float)):
                raise TypeError("Output frequency must be an integer or a float, not {!r}"
                                .format(o_freq))
            if not 10e6 <= o_freq <= 400e6:
                raise ValueError("Output frequency must be between 10 and 400 MHz, not {} MHz"
                                 .format(o_freq / 1e6))

            self.i_domain     = i_domain
            self.i_freq       = int(i_freq)
            self.i_reset_less = bool(i_reset_less)
            self.o_domain     = o_domain
            self.o_freq       = int(o_freq)
            self.fb_internal  = bool(fb_internal)

            self._i_div       = None
            self._fb_div      = None
            self._op          = None
            self._os          = None
            self._os2         = None
            self._os3         = None
            self._2nd_outputs = OrderedDict()
            self._frozen      = False

        @property
        def i_div(self):
            self.compute()
            return self._i_div

        @property
        def fb_div(self):
            self.compute()
            return self._fb_div

        @property
        def op(self):
            self.compute()
            return self._op

        @property
        def os(self):
            self.compute()
            return self._os

        @property
        def os2(self):
            self.compute()
            return self._os2

        @property
        def os3(self):
            self.compute()
            return self._os3

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
            if not 10e6 <= freq <= 400e6:
                raise ValueError("Output frequency must be between 10 and 400 MHz, not {} MHz"
                                 .format(freq / 1e6))
            if not isinstance(phase, (int, float)):
                raise TypeError("Output phase must be an integer or a float, not {!r}"
                                .format(phase))
            if not 0 <= phase <= 360:
                raise ValueError("Output phase must be between 0 and 360 degrees, not {}"
                                 .format(phase))
            if len(self._2nd_outputs) == 3:
                raise ValueError("This PLL can drive at most 3 secondary outputs")
            if domain in self._2nd_outputs:
                raise ValueError("Output domain '{}' has already been added".format(domain))

            self._2nd_outputs[domain] = freq, phase

        def _iter_variants(self):
            for i_div in range(1, 128 + 1):
                pfd_freq = self.i_freq / i_div
                if not 3.125e6 <= pfd_freq <= 400e6:
                    continue
                for fb_div in range(1, 80 + 1):
                    for op_div in range(1, 128 + 1):
                        vco_freq = pfd_freq * fb_div * op_div
                        if not 400e6 <= vco_freq <= 800e6:
                            continue
                        op_freq = vco_freq / op_div
                        if not 10e6 <= op_freq <= 400e6:
                            continue
                        yield (i_div, fb_div, op_div, pfd_freq, op_freq)

        def compute(self):
            """Compute PLL parameters.

            This method is idempotent. As a side-effect of its first call, the visible state of the
            :class:`PLL_LatticeECP5.Parameters` instance becomes immutable (e.g. adding more PLL outputs
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
                i_div, fb_div, op_div, pfd_freq, op_freq = variant
                vco_freq = pfd_freq * fb_div * op_div
                return abs(op_freq - self.o_freq), abs(vco_freq - 600e6), abs(pfd_freq - 200e6)

            i_div, fb_div, op_div, pfd_freq, op_freq = min(variants, key=error)

            vco_freq = pfd_freq * fb_div * op_div
            op_shift = (1 / op_freq) * 0.5

            self._i_div  = i_div
            self._fb_div = fb_div

            self._op = PLL_LatticeECP5.Parameters.Output(
                domain = self.o_domain,
                freq   = op_freq,
                div    = op_div,
                cphase = op_shift * vco_freq,
                fphase = 0,
            )

            for i, (os_domain, (os_freq, os_phase)) in enumerate(self._2nd_outputs.items()):
                os_name   = "_os{}".format(i + 1 if i > 0 else "")
                os_shift  = (1 / os_freq) * os_phase / 360.0
                os_params = PLL_LatticeECP5.Parameters.Output(
                    domain = os_domain,
                    freq   = os_freq,
                    div    = vco_freq // os_freq,
                    cphase = self._op.cphase + (os_shift * vco_freq),
                    fphase = 0,
                )
                setattr(self, os_name, os_params)

            self._frozen = True

    """PLL for Lattice ECP5 FPGAs.

    Parameters
    ----------
    params : :class:`PLL_LatticeECP5.Parameters`
        PLL parameters.

    Attributes
    ----------
    params : :class:`PLL_LatticeECP5.Parameters`
        PLL parameters.
    locked : Signal(), out
        PLL lock status.
    """
    def __init__(self, params):
        if not isinstance(params, PLL_LatticeECP5.Parameters):
            raise TypeError("PLL parameters must be an instance of PLL_LatticeECP5.Parameters, not {!r}"
                            .format(params))

        params.compute()
        self.params = params
        self.locked = Signal()

    def elaborate(self, platform):
        pll_kwargs = {
            "a_ICP_CURRENT"            : 12,
            "a_LPF_RESISTOR"           : 8,
            "a_MFG_ENABLE_FILTEROPAMP" : 1,
            "a_MFG_GMCREF_SEL"         : 2,
            "p_INTFB_WAKE"             : "DISABLED",
            "p_STDBY_ENABLE"           : "DISABLED",
            "p_DPHASE_SOURCE"          : "DISABLED",
            "p_OUTDIVIDER_MUXA"        : "DIVA",
            "p_OUTDIVIDER_MUXB"        : "DIVB",
            "p_OUTDIVIDER_MUXC"        : "DIVC",
            "p_OUTDIVIDER_MUXD"        : "DIVD",

            "i_PHASESEL0"              : Const(0),
            "i_PHASESEL1"              : Const(0),
            "i_PHASEDIR"               : Const(1),
            "i_PHASESTEP"              : Const(1),
            "i_PHASELOADREG"           : Const(1),
            "i_PLLWAKESYNC"            : Const(0),
            "i_ENCLKOP"                : Const(0),

            "o_LOCK"                   : self.locked,

            "a_FREQUENCY_PIN_CLKI"     : int(self.params.i_freq / 1e6),
            "p_CLKI_DIV"               : self.params.i_div,
            "i_CLKI"                   : ClockSignal(self.params.i_domain),

            "a_FREQUENCY_PIN_CLKOP"    : int(self.params.op.freq / 1e6),
            "p_CLKOP_ENABLE"           : "ENABLED",
            "p_CLKOP_DIV"              : self.params.op.div,
            "p_CLKOP_CPHASE"           : self.params.op.cphase,
            "p_CLKOP_FPHASE"           : self.params.op.fphase,
            "o_CLKOP"                  : ClockSignal(self.params.op.domain),
        }

        # Secondary outputs

        if self.params.os is not None:
            pll_kwargs.update({
                "a_FREQUENCY_PIN_CLKOS" : int(self.params.os.freq / 1e6),
                "p_CLKOS_ENABLE"        : "ENABLED",
                "p_CLKOS_DIV"           : self.params.os.div,
                "p_CLKOS_CPHASE"        : self.params.os.cphase,
                "p_CLKOS_FPHASE"        : self.params.os.fphase,
                "o_CLKOS"               : ClockSignal(self.params.os.domain),
            })
        else:
            pll_kwargs.update({
                "p_CLKOS_ENABLE"        : "DISABLED",
            })

        if self.params.os2 is not None:
            pll_kwargs.update({
                "a_FREQUENCY_PIN_CLKOS2" : int(self.params.os2.freq / 1e6),
                "p_CLKOS2_ENABLE"        : "ENABLED",
                "p_CLKOS2_DIV"           : self.params.os2.div,
                "p_CLKOS2_CPHASE"        : self.params.os2.cphase,
                "p_CLKOS2_FPHASE"        : self.params.os2.fphase,
                "o_CLKOS2"               : ClockSignal(self.params.os2.domain),
            })
        else:
            pll_kwargs.update({
                "p_CLKOS2_ENABLE"        : "DISABLED",
            })

        if self.params.os3 is not None:
            pll_kwargs.update({
                "a_FREQUENCY_PIN_CLKOS3" : int(self.params.os3.freq / 1e6),
                "p_CLKOS3_ENABLE"        : "ENABLED",
                "p_CLKOS3_DIV"           : self.params.os3.div,
                "p_CLKOS3_CPHASE"        : self.params.os3.cphase,
                "p_CLKOS3_FPHASE"        : self.params.os3.fphase,
                "o_CLKOS3"               : ClockSignal(self.params.os3.domain),
            })
        else:
            pll_kwargs.update({
                "p_CLKOS3_ENABLE"        : "DISABLED",
            })

        # Reset

        if not self.params.i_reset_less:
            pll_kwargs.update({
                "p_PLLRST_ENA" : "ENABLED",
                "i_RST"        : ResetSignal(self.params.i_domain),
            })
        else:
            pll_kwargs.update({
                "p_PLLRST_ENA" : "DISABLED",
                "i_RST"        : Const(0),
            })

        # Feedback

        pll_kwargs.update({
            "p_CLKFB_DIV" : int(self.params.fb_div),
        })

        if self.params.fb_internal:
            clkintfb = Signal()
            pll_kwargs.update({
                "p_FEEDBK_PATH" : "INT_OP",
                "i_CLKFB"       : clkintfb,
                "o_CLKINTFB"    : clkintfb,
            })
        else:
            pll_kwargs.update({
                "p_FEEDBK_PATH" : "CLKOP",
                "i_CLKFB"       : ClockSignal(self.params.op.domain),
                "o_CLKINTFB"    : Signal(),
            })

        return Instance("EHXPLLL", **pll_kwargs)
