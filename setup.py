from setuptools import setup, find_packages, Extension
from setuptools_scm import get_version

def version():
    version = get_version()
    with open('src/greaseweazle/__init__.py', 'w') as f:
        f.write('__version__ = \'%s\'\n' % version)
    return version

setup(name = 'greaseweazle',
      python_requires = '>=3.7',
      version = version(),
      install_requires = [
          'crcmod',
          'bitarray',
          'pyserial',
          'requests'
      ],
      packages = find_packages('src'),
      package_dir = { '': 'src' },
      package_data = { 'greaseweazle.data': ['*.cfg'] },
      ext_modules = [
          Extension('greaseweazle.optimised.optimised',
                    sources = ['src/greaseweazle/optimised/optimised.c'])
      ],
      entry_points= {
          'console_scripts': ['gw=greaseweazle.cli:main']
      }
)
