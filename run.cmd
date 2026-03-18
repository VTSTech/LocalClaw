@echo off
setlocal

echo ============================================================
echo         LocalClaw R03 - Run Single Example
echo ============================================================
echo.
echo Available examples:
echo.
echo   01 - Basic Agent
echo   02 - Tool Agent
echo   03 - Orchestrator
echo   04 - Comprehensive Test
echo   05 - Tool Tests
echo   06 - Interactive Chat
echo   07 - Model Comparison
echo   08 - Robust Comparison
echo   09 - Expanded Benchmark
echo   10 - Skills Demo
echo   11 - Skill Creator Test
echo.
echo   all     - Run all examples
echo   quick   - Run quick tests (skip benchmarks and interactive)
echo.

set /p CHOICE="Enter choice (01-11, all, quick): "

if "%CHOICE%"=="all" (
    call test.cmd
    exit /b
)

if "%CHOICE%"=="quick" (
    call test-quick.cmd
    exit /b
)

if "%CHOICE%"=="01" ( python examples\01_basic_agent.py & exit /b )
if "%CHOICE%"=="1"  ( python examples\01_basic_agent.py & exit /b )

if "%CHOICE%"=="02" ( python examples\02_tool_agent.py & exit /b )
if "%CHOICE%"=="2"  ( python examples\02_tool_agent.py & exit /b )

if "%CHOICE%"=="03" ( python examples\03_orchestrator.py & exit /b )
if "%CHOICE%"=="3"  ( python examples\03_orchestrator.py & exit /b )

if "%CHOICE%"=="04" ( python examples\04_comprehensive_test.py & exit /b )
if "%CHOICE%"=="4"  ( python examples\04_comprehensive_test.py & exit /b )

if "%CHOICE%"=="05" ( python examples\05_tool_tests.py & exit /b )
if "%CHOICE%"=="5"  ( python examples\05_tool_tests.py & exit /b )

if "%CHOICE%"=="06" ( python examples\06_interactive_chat.py & exit /b )
if "%CHOICE%"=="6"  ( python examples\06_interactive_chat.py & exit /b )

if "%CHOICE%"=="07" ( python examples\07_model_comparison.py & exit /b )
if "%CHOICE%"=="7"  ( python examples\07_model_comparison.py & exit /b )

if "%CHOICE%"=="08" ( python examples\08_robust_comparison.py & exit /b )
if "%CHOICE%"=="8"  ( python examples\08_robust_comparison.py & exit /b )

if "%CHOICE%"=="09" ( python examples\09_expanded_benchmark.py & exit /b )
if "%CHOICE%"=="9"  ( python examples\09_expanded_benchmark.py & exit /b )

if "%CHOICE%"=="10" ( python examples\10_skills_demo.py & exit /b )

if "%CHOICE%"=="11" ( python examples\11_skill_creator_test.py & exit /b )

echo.
echo Invalid choice: %CHOICE%
echo Please enter a number between 01-11, 'all', or 'quick'.
exit /b 1
