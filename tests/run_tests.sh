#!/bin/bash
# MessMate Test Runner
# Usage: bash tests/run_tests.sh [tag]
# Example: bash tests/run_tests.sh smoke

TAG=${1:-""}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="tests/results/${TIMESTAMP}"
mkdir -p ${OUTPUT_DIR}

if [ -n "$TAG" ]; then
    echo "Running tests with tag: ${TAG}"
    robot --include ${TAG} \
          --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
else
    echo "Running all tests"
    robot --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
fi

echo ""
echo "Results saved to: ${OUTPUT_DIR}"
echo "Open ${OUTPUT_DIR}/report.html to view the test report."
