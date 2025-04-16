@echo OFF>nul
IF [%1]==[] GOTO NoParam
filetranslate -a 2 -p %1
GOTO :EndBatch
:NoParam
filetranslate -a 2 
:EndBatch
xcopy ".\translation_out\data\*.json" "translated_game\data\" /E /C /R /K /Y /D