from .. import collect_cxxrtl_src
from . import util


cxxrtl_src_files = [
    *collect_cxxrtl_src(util),
]
