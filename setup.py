from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        if version.tag and not version.distance:
            return version.format_with("")
        else:
            return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme
    }


setup(
    name="lambdasoc",
    use_scm_version=scm_version(),
    author="Jean-François Nguyen",
    author_email="jf@lambdaconcept.com",
    description="A framework for building SoCs with Amaranth",
    #long_description="""TODO""",
    license="BSD",
    setup_requires=["setuptools_scm"],
    install_requires=[
        "jinja2>=3.0",
        "amaranth>=0.3",
        "amaranth-soc",
        "amaranth-stdio",
        "amaranth-boards",
        "minerva",

        #"migen",
        #"litex",
        #"litedram",
    ],
    entry_points={
        "console_scripts": [
            "flterm=lambdasoc.tools.flterm:main [SFL]",
        ]
    },
    extras_require={
        "SFL": ["asyncserial"]
    },
    packages=find_packages(),
    zip_safe=False, # install package as a directory. needed to build the SoC firmware.
    include_package_data=True,
    project_urls={
        "Source Code": "https://github.com/lambdaconcept/lambdasoc",
        "Bug Tracker": "https://github.com/lambdaconcept/lambdasoc/issues",
    },
)
