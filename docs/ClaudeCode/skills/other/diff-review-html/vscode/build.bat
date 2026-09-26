@echo off
rem Build the diff-review-vscode .vsix (Windows version).
rem The POSIX sh version is build.sh in this folder; keep flags, exit codes and behaviour in sync.
rem
rem ASCII only, on purpose: cmd reads this file with the console code page (932 and friends),
rem so non-ASCII bytes are mis-decoded and can even split a rem line into commands.
rem Japanese notes live in build.sh and README.md.
rem
rem Usage:
rem   build.bat            package the .vsix from the existing out\ and media\viewer.html (fast)
rem   build.bat --build    rebuild the viewer and compile first, then package
rem   build.bat --help     show this help
rem
rem Requirements:
rem   - npm ci already run (@vscode/vsce must be in node_modules)
rem   - --build also needs Python 3 (py -3 / python / python3 are tried; PYTHON overrides)
rem
rem Exit codes: 0=ok / 1=missing prerequisite or build failure / 2=bad argument

setlocal
cd /d "%~dp0"

set "BUILD=0"

:parse
if "%~1"=="" goto args_done
if /i "%~1"=="--build" (
  set "BUILD=1"
  shift
  goto parse
)
if /i "%~1"=="-h" goto usage
if /i "%~1"=="--help" goto usage
echo Unknown argument: %~1 1>&2
echo. 1>&2
call :print_usage 1>&2
exit /b 2

:args_done
if not exist "node_modules\.bin\vsce.cmd" (
  echo vsce is not in node_modules. Run npm ci first. 1>&2
  exit /b 1
)

if "%BUILD%"=="1" goto do_build
rem Packaging only: make sure the build output is there. A .vsix without it installs
rem fine but opens nothing, and you would not notice until you tried it.
if not exist "media\viewer.html" goto need_build
if not exist "out\src\extension.js" goto need_build
goto do_package

:do_build
call npm run build
if errorlevel 1 exit /b 1

:do_package
call "node_modules\.bin\vsce.cmd" package --skip-license
if errorlevel 1 exit /b 1
exit /b 0

:need_build
echo Build output is missing: media\viewer.html / out\src\extension.js 1>&2
echo Run with --build (for example: build.bat --build). 1>&2
exit /b 1

:usage
call :print_usage
exit /b 0

:print_usage
echo Build the diff-review-vscode .vsix.
echo.
echo Usage:
echo   build.bat            package from the existing out\ and media\viewer.html (fast)
echo   build.bat --build    rebuild the viewer and compile first, then package
echo   build.bat --help     show this help
echo.
echo Requirements: npm ci done. --build also needs Python 3 (PYTHON overrides the lookup).
goto :eof
