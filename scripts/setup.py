from cx_Freeze import setup, Executable
from greaseweazle import version

buildOptions = dict(
    packages = ['greaseweazle'],
    excludes = ['tkinter', 'test', 'distutils', 'email'],
    include_msvcr = True)

base = 'Console'

executables = [
    Executable('gw.py', base=base)
]

setup(name='Greaseweazle',
      version = f'{version.major}.{version.minor}',
      description = '',
      options = dict(build_exe = buildOptions),
      executables = executables)
