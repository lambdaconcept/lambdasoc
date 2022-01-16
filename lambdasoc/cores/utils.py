def request_bare(platform, name, number):
        """Request bare pins.

        This helper requests pins with `dir="-"` and `xdr=0`, for use cases where implicit I/O
        buffers are undesirable.

        Arguments
        ---------
        platform : :class:`amaranth.build.plat.Platform`
            Target platform.
        name : str
            Resource name.
        number : int
            Resource number.

        Return value
        ------------
        A :class:`Record` providing raw access to pins.
        """
        res = platform.lookup(name, number)
        return platform.request(
            name, number,
            dir={io.name: "-" for io in res.ios},
            xdr={io.name: 0   for io in res.ios},
        )
