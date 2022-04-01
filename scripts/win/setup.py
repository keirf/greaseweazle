from cx_Freeze import setup, Executable

buildOptions = dict(
    packages = ['greaseweazle'],
    excludes = ['tkinter', 'test', 'distutils'],
    include_msvcr = True)

base = 'Console'

executables = [
    Executable('gw.py', base=base)
]

setup(name='Greaseweazle',
      options = dict(build_exe = buildOptions),
      executables = executables)
