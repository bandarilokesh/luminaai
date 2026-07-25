Option Explicit
' Stops the Lumina AI server started by Start-Lumina-Ai.vbs.

Dim fso, scriptDir, pidFile, pidText, wmi, proc, found

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pidFile = scriptDir & "\lumina.pid"
found = False

If fso.FileExists(pidFile) Then
    pidText = Trim(fso.OpenTextFile(pidFile, 1).ReadAll())
    If pidText <> "" Then
        Set wmi = GetObject("winmgmts:\\.\root\cimv2")
        For Each proc In wmi.ExecQuery("Select * from Win32_Process Where ProcessId = " & pidText)
            proc.Terminate()
            found = True
        Next
    End If
    fso.DeleteFile pidFile, True
End If

If found Then
    MsgBox "Lumina AI has been stopped.", vbInformation, "Lumina AI"
Else
    MsgBox "Lumina AI does not appear to be running.", vbInformation, "Lumina AI"
End If
