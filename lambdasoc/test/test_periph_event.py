# amaranth: UnusedElaboratable=no

import unittest
from amaranth import *
from amaranth.back.pysim import *

from ..periph.event import *


def simulation_test(dut, process):
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("test.vcd"):
        sim.run()


class EventSourceTestCase(unittest.TestCase):
    def test_simple(self):
        ev = EventSource()
        self.assertEqual(ev.name, "ev")
        self.assertEqual(ev.mode, "level")

    def test_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            EventSource(name=2)

    def test_mode_wrong(self):
        with self.assertRaisesRegex(ValueError,
                r"Invalid trigger mode 'foo'; must be one of level, rise, fall"):
            ev = EventSource(mode="foo")


class InterruptSourceTestCase(unittest.TestCase):
    def test_simple(self):
        ev_0 = EventSource()
        ev_1 = EventSource()
        dut = InterruptSource((ev_0, ev_1))
        self.assertEqual(dut.name, "dut")
        self.assertEqual(dut.status.width, 2)
        self.assertEqual(dut.pending.width, 2)
        self.assertEqual(dut.enable.width, 2)

    def test_name_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Name must be a string, not 2"):
            InterruptSource((), name=2)

    def test_event_wrong(self):
        with self.assertRaisesRegex(TypeError,
                r"Event source must be an instance of EventSource, not 'foo'"):
            dut = InterruptSource(("foo",))

    def test_events(self):
        ev_0 = EventSource(mode="level")
        ev_1 = EventSource(mode="rise")
        ev_2 = EventSource(mode="fall")
        dut  = InterruptSource((ev_0, ev_1, ev_2))

        def process():
            yield ev_0.stb.eq(1)
            yield ev_1.stb.eq(0)
            yield ev_2.stb.eq(1)
            yield
            self.assertEqual((yield dut.irq), 0)

            yield dut.status.r_stb.eq(1)
            yield
            yield dut.status.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.status.r_data), 0b101)
            yield

            yield dut.enable.w_stb.eq(1)
            yield dut.enable.w_data.eq(0b111)
            yield
            yield dut.enable.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 1)

            yield dut.pending.w_stb.eq(1)
            yield dut.pending.w_data.eq(0b001)
            yield
            yield dut.pending.w_stb.eq(0)
            yield

            yield dut.pending.r_stb.eq(1)
            yield
            yield dut.pending.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.pending.r_data), 0b001)
            self.assertEqual((yield dut.irq), 1)
            yield

            yield ev_0.stb.eq(0)
            yield dut.pending.w_stb.eq(1)
            yield dut.pending.w_data.eq(0b001)
            yield
            yield dut.pending.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

            yield ev_1.stb.eq(1)
            yield dut.pending.r_stb.eq(1)
            yield
            yield dut.pending.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.pending.r_data), 0b010)
            self.assertEqual((yield dut.irq), 1)

            yield dut.pending.w_stb.eq(1)
            yield dut.pending.w_data.eq(0b010)
            yield
            yield dut.pending.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

            yield ev_2.stb.eq(0)
            yield
            yield dut.pending.r_stb.eq(1)
            yield
            yield dut.pending.r_stb.eq(0)
            yield
            self.assertEqual((yield dut.pending.r_data), 0b100)
            self.assertEqual((yield dut.irq), 1)

            yield dut.pending.w_stb.eq(1)
            yield dut.pending.w_data.eq(0b100)
            yield
            yield dut.pending.w_stb.eq(0)
            yield
            yield
            self.assertEqual((yield dut.irq), 0)

        simulation_test(dut, process)
