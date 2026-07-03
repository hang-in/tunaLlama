' tunaLlama HTTP daemon — 창 없이(hidden) 실행하는 셔틀.
' 스케줄 작업이 이 VBS 를 wscript 로 돌려 tunallama-httpd.cmd 를 숨김 창으로 띄운다.
' (cmd 는 pythonw 를 실행하므로 콘솔 창이 하나도 뜨지 않는다.)
Dim sh, here, target
Set sh = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
target = "cmd /c """ & here & "tunallama-httpd.cmd"""
sh.Run target, 0, False   ' 0 = hidden window, False = wait 안 함
