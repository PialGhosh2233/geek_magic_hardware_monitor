' Launches monitor.py with no console window. Used by the "GeekMagic Monitor" scheduled task.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run "pythonw.exe """ & dir & "\monitor.py""", 0, False
