@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo         LocalClaw R03 - BitNet Benchmark Tests
echo ============================================================
echo.
echo Running benchmarks with LOCALCLAW_BACKEND=bitnet
echo.

REM Set BitNet backend
set LOCALCLAW_BACKEND=bitnet

set "COUNT=0"
set "PASSED=0"
set "FAILED=0"

for %%f in (04_comprehensive_test.py 07_model_comparison.py 08_robust_comparison.py) do (
    set /a COUNT+=1
    
    echo ============================================================
    echo [!COUNT!/3] Running: examples\%%f (BitNet)
    echo ============================================================
    echo.
    
    python examples\%%f
    set "EXITCODE=!ERRORLEVEL!"
    
    if !EXITCODE! EQU 0 (
        set /a PASSED+=1
        echo.
        echo [SUCCESS] %%f completed with exit code 0
    ) else (
        set /a FAILED+=1
        echo.
        echo [ERROR] %%f failed with exit code !EXITCODE!
    )
    
    echo.
    echo ------------------------------------------------------------
    echo.
)

echo ============================================================
echo                      SUMMARY
echo ============================================================
echo  Total:  %COUNT% BitNet benchmarks
echo  Passed: %PASSED%
echo  Failed: %FAILED%
echo ============================================================
echo.

if %FAILED% GTR 0 (
    echo Some BitNet tests failed. Please review the output above.
    exit /b 1
) else (
    echo All BitNet benchmarks completed successfully!
    exit /b 0
)
