#!/bin/bash

echo "============================================================"
echo "             LocalClaw R01 - Running All Examples"
echo "============================================================"
echo

COUNT=0
PASSED=0
FAILED=0

for file in 01_basic_agent.py 02_tool_agent.py 03_orchestrator.py 04_comprehensive_test.py 05_tool_tests.py 06_interactive_chat.py 07_model_comparison.py 08_robust_comparison.py 09_expanded_benchmark.py 10_skills_demo.py 11_skill_creator_test.py; do
    ((COUNT++))
    
    echo "============================================================"
    echo "[$COUNT/11] Running: examples/$file"
    echo "============================================================"
    echo
    
    python examples/$file
    EXITCODE=$?
    
    if [ $EXITCODE -eq 0 ]; then
        ((PASSED++))
        echo
        echo "[SUCCESS] $file completed with exit code 0"
    else
        ((FAILED++))
        echo
        echo "[ERROR] $file failed with exit code $EXITCODE"
    fi
    
    echo
    echo "------------------------------------------------------------"
    echo
done

echo "============================================================"
echo "                      SUMMARY"
echo "============================================================"
echo " Total:  $COUNT examples"
echo " Passed: $PASSED"
echo " Failed: $FAILED"
echo "============================================================"
echo

if [ $FAILED -gt 0 ]; then
    echo "Some tests failed. Please review the output above."
    exit 1
else
    echo "All examples completed successfully!"
    exit 0
fi
