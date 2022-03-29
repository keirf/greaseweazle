from setuptools import setup, find_packages, Extension

def v(filename='VERSION'):
    with open(filename, 'r') as fd:
        return fd.read()

setup(name='greaseweazle',
      version = v(),
      description = '',
      install_requires=[
          'crcmod',
          'bitarray',
          'pyserial',
          'requests',
          'wheel'
      ],
      packages=find_packages(),
      ext_modules=[Extension('gwoptimised', sources = ['c_ext/optimised.c'])],
      entry_points={
          'console_scripts': ['gw=greaseweazle.cli:main']}
)
