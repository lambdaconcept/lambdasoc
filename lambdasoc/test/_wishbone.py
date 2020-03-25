def wb_read(bus, addr, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.sel.eq(sel)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    data = (yield bus.dat_r)
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    return data

def wb_write(bus, addr, data, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.we.eq(1)
    yield bus.sel.eq(sel)
    yield bus.dat_w.eq(data)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.we.eq(0)
