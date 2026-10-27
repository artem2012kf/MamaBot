$source = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class FileLockFinder {
    [StructLayout(LayoutKind.Sequential)]
    struct RM_UNIQUE_PROCESS { public int dwProcessId; public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime; }

    const int RmRebootReasonNone = 0;
    const int CCH_RM_MAX_APP_NAME = 255;
    const int CCH_RM_MAX_SVC_NAME = 63;

    enum RM_APP_TYPE { RmUnknownApp = 0, RmMainWindow = 1, RmOtherWindow = 2, RmService = 3, RmExplorer = 4, RmConsole = 5, RmCritical = 1000 }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct RM_PROCESS_INFO {
        public RM_UNIQUE_PROCESS Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_APP_NAME + 1)] public string strAppName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_SVC_NAME + 1)] public string strServiceShortName;
        public RM_APP_TYPE ApplicationType;
        public uint AppStatus;
        public uint TSSessionId;
        [MarshalAs(UnmanagedType.Bool)] public bool bRestartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    static extern int RmRegisterResources(uint pSessionHandle, uint nFiles, string[] rgsFilenames,
        uint nApplications, [In] RM_UNIQUE_PROCESS[] rgApplications, uint nServices, string[] rgsServiceNames);

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Auto)]
    static extern int RmStartSession(out uint pSessionHandle, int dwSessionFlags, string strSessionKey);

    [DllImport("rstrtmgr.dll")]
    static extern int RmEndSession(uint pSessionHandle);

    [DllImport("rstrtmgr.dll")]
    static extern int RmGetList(uint dwSessionHandle, out uint pnProcInfoNeeded,
        ref uint pnProcInfo, [In, Out] RM_PROCESS_INFO[] rgAffectedApps, ref uint lpdwRebootReasons);

    public static List<int> FindLockers(string path) {
        uint handle;
        string key = Guid.NewGuid().ToString();
        var pids = new List<int>();
        int res = RmStartSession(out handle, 0, key);
        if (res != 0) throw new Exception("RmStartSession failed: " + res);
        try {
            uint pnProcInfoNeeded = 0, pnProcInfo = 0, lpdwRebootReasons = RmRebootReasonNone;
            string[] resources = new string[] { path };
            res = RmRegisterResources(handle, 1, resources, 0, null, 0, null);
            if (res != 0) throw new Exception("RmRegisterResources failed: " + res);
            res = RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, null, ref lpdwRebootReasons);
            if (res == 234) {
                var processInfo = new RM_PROCESS_INFO[pnProcInfoNeeded];
                pnProcInfo = pnProcInfoNeeded;
                res = RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, processInfo, ref lpdwRebootReasons);
                if (res == 0) {
                    for (int i = 0; i < pnProcInfo; i++) pids.Add(processInfo[i].Process.dwProcessId);
                }
            }
        } finally { RmEndSession(handle); }
        return pids;
    }
}
'@
Add-Type -TypeDefinition $source -Language CSharp

foreach ($f in $args) {
    if (Test-Path -LiteralPath $f) {
        $pids = [FileLockFinder]::FindLockers($f)
        Write-Host "=== $f ==="
        if ($pids.Count -eq 0) { Write-Host "  RM: дескрипторов не найдено" }
        foreach ($p in $pids) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            Write-Host ("  PID {0}: {1}" -f $p, $(if ($proc) { $proc.ProcessName } else { "<процесс уже завершён>" }))
        }
    } else {
        Write-Host "=== $f === НЕ НАЙДЕН"
    }
}
