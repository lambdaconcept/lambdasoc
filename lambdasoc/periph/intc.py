from amaranth import *

from amaranth_soc.periph import ConstantMap

from . import Peripheral, IRQLine


__all__ = ["InterruptController", "GenericInterruptController"]


class InterruptController(Peripheral):
    """Interrupt controller base class."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__irq_lines = set()
        self.__irq_map   = dict()

    @property
    def constant_map(self):
        return ConstantMap(**{
            line.name.upper(): index for index, line in self.iter_irqs()
        })

    def add_irq(self, line, index):
        """Add an IRQ line.

        Parameters
        ----------
        line : :class:`IRQLine`
            IRQ line.
        index : int
            IRQ index.

        Exceptions
        ----------
        Raises :exn:`ValueError` if ``line`` is added twice, or if ``index`` is already used.
        """
        if not isinstance(line, IRQLine):
            raise TypeError("IRQ line must be an instance of IRQLine, not {!r}"
                            .format(line))
        if not isinstance(index, int) or index < 0:
            raise ValueError("IRQ index must be a non-negative integer, not {!r}"
                             .format(index))
        if line in self.__irq_lines:
            raise ValueError("IRQ line {!r} has already been mapped to IRQ index {}"
                             .format(line, self.find_index(line)))
        if index in self.__irq_map:
            raise ValueError("IRQ index {} has already been mapped to IRQ line {!r}"
                             .format(index, self.__irq_map[index]))
        self.__irq_lines.add(line)
        self.__irq_map[index] = line

    def iter_irqs(self):
        """Iterate IRQ lines.

        Yield values
        ------------
        A tuple ``index, line`` describing an IRQ line and its index.
        """
        yield from sorted(self.__irq_map.items())

    def find_index(self, line):
        """Find the index at which an IRQ line is mapped.

        Parameters
        ----------
        line : :class:`IRQLine`
            IRQ line.

        Return value
        ------------
        The index at which ``line`` is mapped, if present.

        Exceptions
        ----------
        Raises :exn:`KeyError` if ``line`` is not present.
        """
        for irq_index, irq_line in self.iter_irqs():
            if line is irq_line:
                return irq_index
        raise KeyError(line)


class GenericInterruptController(InterruptController, Elaboratable):
    """Generic interrupt controller.

    An interrupt "controller" acting as a passthrough for IRQ lines. Useful for CPU cores that do
    interrupt management themselves.

    Parameters
    ----------
    width : int
        Output width.

    Attributes
    ----------
    width : int
        Output width.
    ip : Signal, out
        Pending IRQs.
    """
    def __init__(self, *, width):
        super().__init__(src_loc_at=2)
        if not isinstance(width, int) or width <= 0:
            raise ValueError("Width must be a strictly positive integer, not {!r}"
                             .format(width))
        self.width = width
        self.ip    = Signal(width)

    def add_irq(self, line, index):
        __doc__ = InterruptController.add_irq.__doc__
        if not isinstance(index, int) or index not in range(0, self.width):
            raise ValueError("IRQ index must be an integer ranging from 0 to {}, not {!r}"
                             .format(self.width - 1, index))
        super().add_irq(line, index)

    def elaborate(self, platform):
        m = Module()

        for irq_index, irq_line in self.iter_irqs():
            m.d.comb += self.ip[irq_index].eq(irq_line)

        return m
