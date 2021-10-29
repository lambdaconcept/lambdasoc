def collect_cxxrtl_src(package):
    assert hasattr(package, "cxxrtl_src_files")
    for module_name, subdirs, src_file in package.cxxrtl_src_files:
        basedir = package.__name__.split(".")[-1]
        yield module_name, (basedir, *subdirs), src_file


from . import include


cxxrtl_src_files = [
    *collect_cxxrtl_src(include),
]
