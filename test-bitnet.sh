#!/bin/bash

echo "============================================================"
echo "        LocalClaw R03 - BitNet Benchmark Tests"
echo "============================================================"
echo
echo "Running benchmarks with LOCALCLAW_BACKEND=bitnet"
echo

# Set BitNet backend
export LOCALCLAW_BACKEND=bitnet

COUNT=0
PASSED=0
FAILED=0

for file in 04_comprehensive_test.py 07_model_comparison.py 08_robust_comparison.py; do
    ((COUNT++))
    
    echo "============================================================"
    echo "[$COUNT/3] Running: examples/$file (BitNet)"
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
echo " Total:  $COUNT BitNet benchmarks"
echo " Passed: $PASSED"
echo " Failed: $FAILED"
echo "============================================================"
echo

if [ $FAILED -gt 0 ]; then
    echo "Some BitNet tests failed. Please review the output above."
    exit 1
else
    echo "All BitNet benchmarks completed successfully!"
    exit 0
fi
