@echo off
rem diff-review-vscode の .vsix を作る（Windows 版）。
rem POSIX sh 版は同ディレクトリの build.sh（引数・終了コード・メッセージを一致させること）。
rem
rem 使い方:
rem   build.bat            いまある out\ と media\viewer.html から .vsix を作る（速い）
rem   build.bat --build    画面の生成とコンパイルからやり直してから .vsix を作る
rem   build.bat --help     この説明
rem
rem 前提:
rem   - npm ci 済み（node_modules に @vscode/vsce が要る）
rem   - --build のときは Python 3 も要る（画面を ..\diff_review.py view から作るため。
rem     python3 以外の名前で入っているなら環境変数 PYTHON で指定する）
rem
rem 終了コード: 0=成功 / 1=前提が足りない・ビルド失敗 / 2=引数が違う

rem このファイルは UTF-8。既定のコードページ（932 等）のままだと日本語のメッセージが
rem 化けるので、この窓を UTF-8 にしてから進む（chcp は環境変数ではないので endlocal では戻らない）。
setlocal
chcp 65001 >nul
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
echo 不明な引数: %~1 1>&2
echo. 1>&2
call :print_usage 1>&2
exit /b 2

:args_done
if not exist "node_modules\.bin\vsce.cmd" (
  echo node_modules に vsce がありません。先に npm ci を実行してください。 1>&2
  exit /b 1
)

if "%BUILD%"=="1" goto do_build
rem 作り直さないときは、中身が揃っているかだけ確かめる。欠けたままだと
rem 「入るけれど何も開けない .vsix」ができてしまい、入れてみるまで気づけない。
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
echo ビルド成果物がありません: media\viewer.html / out\src\extension.js 1>&2
echo --build を付けて実行してください（例: build.bat --build）。 1>&2
exit /b 1

:usage
call :print_usage
exit /b 0

rem 説明。build.sh は先頭のコメントをそのまま出すが、cmd で同じことをやると
rem 壊れやすいので、ここは素直に並べる（上のコメントと同じ内容にすること）。
:print_usage
echo diff-review-vscode の .vsix を作る。
echo.
echo 使い方:
echo   build.bat            いまある out\ と media\viewer.html から .vsix を作る（速い）
echo   build.bat --build    画面の生成とコンパイルからやり直してから .vsix を作る
echo   build.bat --help     この説明
echo.
echo 前提: npm ci 済み。--build のときは Python 3 も要る（環境変数 PYTHON で名前を指定できる）。
goto :eof
