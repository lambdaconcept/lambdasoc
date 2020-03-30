# A framework for building SoCs with nMigen

**LambdaSoC is a work in progress. Please keep in mind that some interfaces will undergo breaking changes as they evolve and/or get moved [upstream][nmigen-soc].**

## Installation

```
git clone https://github.com/lambdaconcept/lambdasoc
git submodule update --init --recursive

pip install -r requirements.txt
python setup.py install
```

## Quick start

Let's build and run the SoC example at [examples/sram_soc.py][sram_soc]. It is composed of a [Minerva][minerva] CPU, SRAM storage, an UART and a timer.

##### Requirements
* A `riscv64-unknown-elf` GNU toolchain, to build the first-stage bootloader
* A [supported platform][nmigen-boards] with enough resources to fit the SoC

Here, we build the SoC for the `nmigen_boards.arty_a7.ArtyA7Platform`:
```
python examples/sram_soc.py --baudrate=9600 nmigen_boards.arty_a7.ArtyA7Platform
```

The bootloader shell can be accessed from the serial port:
```
flterm --speed=9600 /dev/ttyUSB1

LambdaSoC BIOS
(c) Copyright 2007-2020 M-Labs Limited
(c) Copyright 2020 LambdaConcept
Built Mar 26 2020 13:41:04

BIOS CRC passed (c402e7e2)
BIOS>
```

The `help` command lists available commands.

## License

LambdaSoC is released under the permissive two-clause BSD license. See LICENSE file for full copyright and license information.

[nmigen-soc]: https://github.com/nmigen/nmigen-soc
[minerva]: https://github.com/lambdaconcept/minerva
[nmigen-boards]: https://github.com/nmigen/nmigen-boards
[sram_soc]: https://github.com/lambdaconcept/lambdasoc/blob/master/examples/sram_soc.py
