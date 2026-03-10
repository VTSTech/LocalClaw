@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo         LocalClaw R01 - Quick Test (Non-Interactive)
echo ============================================================
echo.
echo Skips: 06_interactive_chat, 07-09 benchmarks (long running)
echo.

set "COUNT=0"
set "PASSED=0"
set "FAILED=0"

for %%f in (01_basic_agent.py 02_tool_agent.py 03_orchestrator.py 04_comprehensive_test.py 05_tool_tests.py 10_skills_demo.py 11_skill_creator_test.py) do (
    set /a COUNT+=1
    
    echo ============================================================
    echo [!COUNT!/7] Running: examples\%%f
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
echo  Total:  %COUNT% examples
echo  Passed: %PASSED%
echo  Failed: %FAILED%
echo ============================================================
echo.

if %FAILED% GTR 0 (
    echo Some tests failed. Please review the output above.
    exit /b 1
) else (
    echo All quick tests completed successfully!
    exit /b 0
)
