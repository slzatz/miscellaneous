from distutils.core import setup, Extension
from Cython.Build import cythonize

ext = Extension("prime_mod",
                sources=["prime_mod.pyx", "primelib.c"])
setup(
    ext_modules=cythonize([ext])
)
