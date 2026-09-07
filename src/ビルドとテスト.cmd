@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=C:\Users\ewg2411-03\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PY%" set PY=python
echo === ビルド ===
"%PY%" build.py || goto :fail
echo.
echo === テスト（ヘッドレスブラウザで実機同様に操作） ===
"%PY%" test_app.py || goto :fail
echo.
echo === 公開（git commit と push） ===
cd /d "%~dp0\.."
git add -A
git diff --cached --quiet && echo 変更なし（公開済みと同じ）&& goto :done
set MSG=%~1
if "%MSG%"=="" set MSG=build %date% %time:~0,5%
git commit -q -m "%MSG%" || goto :fail
git push -q origin main || goto :fail
echo push しました。1〜2分で https://nekoze32.github.io/boki2-trainer/ に反映されます。
:done
echo.
echo すべて通りました。
pause
exit /b 0
:fail
echo.
echo *** 失敗があります。上のメッセージを確認してください（push はしていません） ***
pause
exit /b 1
