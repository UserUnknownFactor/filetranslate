@echo off>nul
pushd www\data
setlocal enableDelayedExpansion
set "replacer=.json"
set "original=_strings.csv"
for /f "tokens=*" %%a in ('dir /b /OD 2^>nul ^| findstr /i "_strings.csv$"') do (
  set str=%%a
  set newest=!str:%original%=%replacer%!
)
endlocal & (set newest=%newest%)
popd
build %newest%