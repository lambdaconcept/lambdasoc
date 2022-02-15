#amaranth: UnusedElaboratable=no

import unittest

from amaranth import *
from amaranth.back.pysim import *

from ..periph import IRQLine
from ..periph.intc import *


class InterruptControllerTestCase(unittest.TestCase):
    def test_add_irq_wrong_line(self):
        intc = InterruptController()
        with self.assertRaisesRegex(TypeError,
                r"IRQ line must be an instance of IRQLine, not 'foo'"):
            intc.add_irq("foo", 0)

    def test_add_irq_wrong_index(self):
        intc = InterruptController()
        with self.assertRaisesRegex(ValueError,
                r"IRQ index must be a non-negative integer, not 'bar'"):
            intc.add_irq(IRQLine(name="foo"), "bar")
        with self.assertRaisesRegex(ValueError,
                r"IRQ index must be a non-negative integer, not -1"):
            intc.add_irq(IRQLine(name="foo"), -1)

    def test_add_irq_line_twice(self):
        intc = InterruptController()
        line = IRQLine()
        with self.assertRaisesRegex(ValueError,
                r"IRQ line \(sig line\) has already been mapped to IRQ index 0"):
            intc.add_irq(line, 0)
            intc.add_irq(line, 1)

    def test_add_irq_index_twice(self):
        intc = InterruptController()
        line_0 = IRQLine()
        line_1 = IRQLine()
        with self.assertRaisesRegex(ValueError,
                r"IRQ index 0 has already been mapped to IRQ line \(sig line_0\)"):
            intc.add_irq(line_0, 0)
            intc.add_irq(line_1, 0)

    def test_iter_irqs(self):
        intc = InterruptController()
        line_0 = IRQLine()
        line_1 = IRQLine()
        intc.add_irq(line_0, 0)
        intc.add_irq(line_1, 1)
        self.assertEqual(list(intc.iter_irqs()), [
            (0, line_0),
            (1, line_1),
        ])

    def test_find_index(self):
        intc = InterruptController()
        line_0 = IRQLine()
        line_1 = IRQLine()
        intc.add_irq(line_0, 0)
        intc.add_irq(line_1, 1)
        self.assertEqual(intc.find_index(line_0), 0)
        self.assertEqual(intc.find_index(line_1), 1)

    def test_find_index_absent(self):
        intc = InterruptController()
        line = IRQLine()
        with self.assertRaises(KeyError):
            intc.find_index(line)


class GenericInterruptControllerTestCase(unittest.TestCase):
    def test_wrong_width(self):
        with self.assertRaisesRegex(ValueError,
                r"Width must be a strictly positive integer, not 'foo'"):
            intc = GenericInterruptController(width="foo")
        with self.assertRaisesRegex(ValueError,
                r"Width must be a strictly positive integer, not 0"):
            intc = GenericInterruptController(width=0)

    def test_add_irq_wrong_index(self):
        intc = GenericInterruptController(width=8)
        line = IRQLine()
        with self.assertRaisesRegex(ValueError,
                r"IRQ index must be an integer ranging from 0 to 7, not 8"):
            intc.add_irq(line, 8)

    def test_passthrough(self):
        dut = GenericInterruptController(width=8)
        line_0 = IRQLine()
        line_1 = IRQLine()
        dut.add_irq(line_0, 0)
        dut.add_irq(line_1, 1)

        def process():
            self.assertEqual((yield dut.ip), 0b00)

            yield line_0.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield dut.ip), 0b01)

            yield line_1.eq(1)
            yield Delay(1e-6)
            self.assertEqual((yield dut.ip), 0b11)

        sim = Simulator(dut)
        sim.add_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()
