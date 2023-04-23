@echo OFF>nul
IF [%1]==[] GOTO NoParam
filetranslate -a 2 -p %1
GOTO :EndBatch
:NoParam
filetranslate -a 2 
:EndBatch