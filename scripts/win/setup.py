from cx_Freeze import setup, Executable

# Windows 32-bit build: We need to explicitly point at the 32-bit DLLs early.
import sys, os
if sys.maxsize <= 2**32:
    new_paths = ['C:\\Windows\\SysWOW64\\downlevel']
    old_paths = os.environ['PATH'].split(os.pathsep)
    os.environ['PATH'] = os.pathsep.join(new_paths + old_paths)
    bin_path_includes = new_paths
else:
    bin_path_includes = []

buildOptions = dict(
    packages = ['greaseweazle'],
    excludes = ['tkinter', 'test', 'distutils'],
    bin_path_includes = bin_path_includes,
    include_msvcr = True)

base = 'Console'

executables = [
    Executable('gw.py', base=base)
]

setup(name='Greaseweazle',
      options = dict(build_exe = buildOptions),
      executables = executables)
