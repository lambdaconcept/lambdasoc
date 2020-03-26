from abc import ABCMeta, abstractproperty


__all__ = ["CPU"]


class CPU(metaclass=ABCMeta):
    """TODO
    """
    name       = abstractproperty()
    arch       = abstractproperty()
    byteorder  = abstractproperty()
    data_width = abstractproperty()
    reset_addr = abstractproperty()
    muldiv     = abstractproperty()
