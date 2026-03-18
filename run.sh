#!/bin/bash

echo "============================================================"
echo "        LocalClaw R03 - Run Single Example"
echo "============================================================"
echo
echo "Available examples:"
echo
echo "  01 - Basic Agent"
echo "  02 - Tool Agent"
echo "  03 - Orchestrator"
echo "  04 - Comprehensive Test"
echo "  05 - Tool Tests"
echo "  06 - Interactive Chat"
echo "  07 - Model Comparison"
echo "  08 - Robust Comparison"
echo "  09 - Expanded Benchmark"
echo "  10 - Skills Demo"
echo "  11 - Skill Creator Test"
echo
echo "  all     - Run all examples"
echo "  quick   - Run quick tests (skip benchmarks and interactive)"
echo

read -p "Enter choice (01-11, all, quick): " CHOICE

case "$CHOICE" in
    all)
        ./test.sh
        exit $?
        ;;
    quick)
        ./test-quick.sh
        exit $?
        ;;
    01|1)
        python examples/01_basic_agent.py
        exit $?
        ;;
    02|2)
        python examples/02_tool_agent.py
        exit $?
        ;;
    03|3)
        python examples/03_orchestrator.py
        exit $?
        ;;
    04|4)
        python examples/04_comprehensive_test.py
        exit $?
        ;;
    05|5)
        python examples/05_tool_tests.py
        exit $?
        ;;
    06|6)
        python examples/06_interactive_chat.py
        exit $?
        ;;
    07|7)
        python examples/07_model_comparison.py
        exit $?
        ;;
    08|8)
        python examples/08_robust_comparison.py
        exit $?
        ;;
    09|9)
        python examples/09_expanded_benchmark.py
        exit $?
        ;;
    10)
        python examples/10_skills_demo.py
        exit $?
        ;;
    11)
        python examples/11_skill_creator_test.py
        exit $?
        ;;
    *)
        echo
        echo "Invalid choice: $CHOICE"
        echo "Please enter a number between 01-11, 'all', or 'quick'."
        exit 1
        ;;
esac
