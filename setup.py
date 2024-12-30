from setuptools import setup, find_packages, Extension
from setuptools_scm import get_version

import platform
if platform.system() == 'Linux':
    extra_compile_args = ['-Wall', '-Werror']
else:
    extra_compile_args = []

def version():
    version = get_version()
    with open('src/greaseweazle/__init__.py', 'w') as f:
        f.write('__version__ = \'%s\'\n' % version)
    return version

setup(name = 'greaseweazle',
      python_requires = '>=3.8',
      version = version(),
      install_requires = [
          'crcmod',
          'bitarray>=3',
          'pyserial',
          'requests'
      ],
      packages = find_packages('src'),
      package_dir = { '': 'src' },
      package_data = { 'greaseweazle.data': ['*.cfg'] },
      ext_modules = [
          Extension('greaseweazle.optimised.optimised',
                    sources = ['src/greaseweazle/optimised/optimised.c',
                               'src/greaseweazle/optimised/apple_gcr_6a2.c',
                               'src/greaseweazle/optimised/apple2.c',
                               'src/greaseweazle/optimised/c64.c',
                               'src/greaseweazle/optimised/mac.c',
                               'src/greaseweazle/optimised/td0_lzss.c'],
                    extra_compile_args = extra_compile_args)
      ],
      entry_points= {
          'console_scripts': ['gw=greaseweazle.cli:main']
      }
)
