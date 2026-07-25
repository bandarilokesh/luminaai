Option Explicit
' Lumina AI - silent launcher.
' Double-click this file to start the app with zero visible windows;
' your browser opens automatically once the server is ready.
' Run Stop-Lumina-Ai.vbs to shut it down again.

Dim fso, shell, scriptDir, venvPython, pidFile, logsDir, outLog, qq, fullCmd
Dim wmi, colProcs, p, pid, pidText, isRunning, proc, f, tries

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvPython = scriptDir & "\.venv\Scripts\pythonw.exe"
pidFile = scriptDir & "\lumina.pid"
logsDir = scriptDir & "\logs"
outLog = logsDir & "\launcher.log"

' If a server is already running (per the pid file), just open the browser.
isRunning = False
If fso.FileExists(pidFile) Then
    pidText = Trim(fso.OpenTextFile(pidFile, 1).ReadAll())
    If pidText <> "" Then
        Set wmi = GetObject("winmgmts:\\.\root\cimv2")
        For Each proc In wmi.ExecQuery("Select ProcessId from Win32_Process Where ProcessId = " & pidText)
            isRunning = True
        Next
    End If
End If

If isRunning Then
    shell.Run "http://127.0.0.1:8000", 1, False
    WScript.Quit 0
End If

If Not fso.FileExists(venvPython) Then
    MsgBox "Could not find " & venvPython & vbCrLf & vbCrLf & _
           "Set up the project first:" & vbCrLf & _
           "  python -m venv .venv" & vbCrLf & _
           "  .venv\Scripts\pip install -r requirements.txt", _
           vbCritical, "Lumina AI"
    WScript.Quit 1
End If

If Not fso.FolderExists(logsDir) Then fso.CreateFolder(logsDir)

' pythonw.exe has no console, so sys.stdout/stderr are None unless something
' gives it real output handles - route them to a log file via a hidden cmd.exe
' wrapper (window style 0 keeps it invisible for its whole lifetime).
qq = Chr(34)
fullCmd = "cmd /c " & qq & qq & venvPython & qq & _
    " -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 >> " & _
    qq & outLog & qq & " 2>&1" & qq

shell.CurrentDirectory = scriptDir
shell.Run fullCmd, 0, False

' Look up the PID we just started (read-only WMI query) so Stop-Lumina-Ai.vbs
' can shut down this exact process later.
pid = ""
For tries = 1 To 20
    WScript.Sleep 500
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    Set colProcs = wmi.ExecQuery( _
        "Select ProcessId, CommandLine from Win32_Process Where Name='pythonw.exe'")
    For Each p In colProcs
        If InStr(1, p.CommandLine, "uvicorn", vbTextCompare) > 0 _
           And InStr(1, p.CommandLine, "backend.main", vbTextCompare) > 0 Then
            pid = p.ProcessId
        End If
    Next
    If pid <> "" Then Exit For
Next

If pid <> "" Then
    Set f = fso.CreateTextFile(pidFile, True)
    f.WriteLine pid
    f.Close
End If

' Give the server the rest of its startup time (loading the AI models takes a
' few seconds the first time), then open it like a native app.
WScript.Sleep 6000
shell.Run "http://127.0.0.1:8000", 1, False
