"""Run an owned native test on an inactive Windows desktop; never switch desktops.

The keeper retains the desktop and process handles until the child exits. All
input/capture still goes through the game's test adapter, not OS input APIs.
"""
from pathlib import Path
import argparse,ctypes,json,msvcrt,os,subprocess,time
from ctypes import wintypes as W

class Startup(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
        ('x',W.DWORD),('y',W.DWORD),('width',W.DWORD),('height',W.DWORD),('charsX',W.DWORD),('charsY',W.DWORD),
        ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reservedBytes',W.WORD),('reservedPtr',ctypes.c_void_p),
        ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class Process(ctypes.Structure):
    _fields_=[('handle',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]

def save(path,value):
    pending=path.with_suffix('.pending')
    pending.write_text(json.dumps(value,indent=2),encoding='utf-8');pending.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('configuration',type=Path);args=p.parse_args()
    config=json.loads(args.configuration.read_text(encoding='utf-8'));run=args.configuration.parent
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.CreateDesktopW.argtypes=[W.LPCWSTR,W.LPCWSTR,ctypes.c_void_p,W.DWORD,W.DWORD,ctypes.c_void_p];user.CreateDesktopW.restype=W.HANDLE
    user.CloseDesktop.argtypes=[W.HANDLE];user.CloseDesktop.restype=W.BOOL
    kernel.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,W.BOOL,W.DWORD,ctypes.c_void_p,W.LPCWSTR,ctypes.POINTER(Startup),ctypes.POINTER(Process)];kernel.CreateProcessW.restype=W.BOOL
    kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.WaitForSingleObject.restype=W.DWORD
    kernel.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];kernel.GetExitCodeProcess.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.TerminateProcess.argtypes=[W.HANDLE,W.UINT];kernel.TerminateProcess.restype=W.BOOL
    kernel.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,ctypes.POINTER(W.BOOL)];kernel.IsProcessInJob.restype=W.BOOL
    kernel.GetCurrentProcess.restype=W.HANDLE
    keeperInJob=W.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(),None,ctypes.byref(keeperInJob)):raise ctypes.WinError(ctypes.get_last_error())
    if os.environ.get('CODEX_HEAVY_JOB') and not keeperInJob.value:
        raise RuntimeError('Native keeper escaped the resource job; use the real Python executable, not a WindowsApps alias')
    owner=kernel.OpenProcess(0x100000,False,os.getppid())
    if not owner:raise ctypes.WinError(ctypes.get_last_error())
    desktopName='PZ-Test-'+str(os.getpid())+'-'+str(time.time_ns())
    desktop=user.CreateDesktopW(desktopName,None,None,0,0x10000000,None)
    if not desktop: raise ctypes.WinError(ctypes.get_last_error())
    info=Process()
    try:
        with open(os.devnull,'rb') as stdin,(run/'stdout.log').open('wb') as stdout,(run/'stderr.log').open('wb') as stderr:
            handles=[msvcrt.get_osfhandle(stream.fileno()) for stream in (stdin,stdout,stderr)]
            for handle in handles:os.set_handle_inheritable(handle,True)
            startup=Startup();startup.cb=ctypes.sizeof(Startup);startup.desktop=desktopName
            startup.flags=0x100|0x1;startup.show=0;startup.stdin,startup.stdout,startup.stderr=handles
            command=ctypes.create_unicode_buffer(subprocess.list2cmdline(config['command']))
            try:
                if not kernel.CreateProcessW(config['command'][0],command,None,None,True,subprocess.CREATE_NO_WINDOW,None,config['cwd'],ctypes.byref(startup),ctypes.byref(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                for handle in handles:os.set_handle_inheritable(handle,False)
            gameInJob=W.BOOL()
            if not kernel.IsProcessInJob(info.handle,None,ctypes.byref(gameInJob)):raise ctypes.WinError(ctypes.get_last_error())
            record={'pid':info.pid,'keeperPid':os.getpid(),'desktop':desktopName,'desktopSwitched':False,
                'keeperInJob':bool(keeperInJob.value),'gameInJob':bool(gameInJob.value),'startedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}
            save(run/'native-session-started.json',record)
            while True:
                result=kernel.WaitForSingleObject(info.handle,1000)
                if result==0:break
                if result!=258:raise ctypes.WinError(ctypes.get_last_error())
                if kernel.WaitForSingleObject(owner,0)==0:
                    record['ownerExited']=True
                    if not kernel.TerminateProcess(info.handle,137):raise ctypes.WinError(ctypes.get_last_error())
                    if kernel.WaitForSingleObject(info.handle,10000)!=0:raise RuntimeError('Owned game did not stop')
                    break
            code=W.DWORD()
            if not kernel.GetExitCodeProcess(info.handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
            record.update(exitCode=code.value,finishedAt=time.strftime('%Y-%m-%dT%H:%M:%S'))
            save(run/'native-session-exit.json',record)
    finally:
        if info.thread:kernel.CloseHandle(info.thread)
        if info.handle:kernel.CloseHandle(info.handle)
        kernel.CloseHandle(owner)
        user.CloseDesktop(desktop)

if __name__=='__main__':main()
