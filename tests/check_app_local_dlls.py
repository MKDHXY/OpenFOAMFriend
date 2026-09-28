import sys,ctypes,json
from pathlib import Path
import vtk,gmsh,PySide6
gmsh.initialize();gmsh.finalize()
kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p];kernel.GetModuleHandleW.restype=ctypes.c_void_p;kernel.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint];kernel.GetModuleFileNameW.restype=ctypes.c_uint
runtime=Path(sys.executable).parent.resolve();paths={}
for name in ('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll'):
    handle=kernel.GetModuleHandleW(name);assert handle,name
    buffer=ctypes.create_unicode_buffer(32768);assert kernel.GetModuleFileNameW(handle,buffer,len(buffer));path=Path(buffer.value).resolve();assert path.is_relative_to(runtime),(name,str(path));paths[name]=str(path)
print(json.dumps(dict(runtime=str(runtime),loaded_app_local_MSVC=paths),indent=2))
