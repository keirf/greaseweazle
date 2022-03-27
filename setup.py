from setuptools import setup, find_packages, Extension

setup(name='greaseweazle',
      version = '0.39',
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
