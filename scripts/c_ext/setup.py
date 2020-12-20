from distutils.core import setup, Extension

module1 = Extension('optimised', sources = ['optimised.c'])

setup(name = 'optimised',
      ext_modules = [module1])
