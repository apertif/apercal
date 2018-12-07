from setuptools import setup, find_packages

__version__ = '2.1'

scripts = []

install_requires = [
    'numpy',
    'notebook',
    'matplotlib',
    'astropy',
    'astroquery',
    'pandas',
    'drive-casa',
    'python-casacore',
    'aipy',
    'pymp-pypi',
    'typing',
    'bdsf'
]


setup(
    name="apercal",
    version=__version__,
    scripts=scripts,
    packages=find_packages(),
    install_requires=install_requires,
    tests_require=['pytest'],
    include_package_data=True,
    author="Bjoern Adebahr",
    author_email="adebahr@astron.nl",
    description="Scientific Compute Container Spec Parser",
    license="GPL2",
    keywords="science astronomy radio",
    url="https://github.com/apertif/apercal",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 2.7",
        "Topic :: Scientific/Engineering",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Operating System Kernels :: Linux",
        ]
)
