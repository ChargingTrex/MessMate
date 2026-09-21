#!/bin/bash
# MessMate Test Runner
# Usage: bash tests/run_tests.sh [tag]
# Example: bash tests/run_tests.sh smoke

# Committee suites can run against an in-memory backend instead of a live
# spreadsheet — start it first, then point the run at it:
#   python test/fake_server.py 5001
#   BASE_URL=http://127.0.0.1:5001 bash tests/run_tests.sh
#
# CHROME_BINARY / CHROME_DRIVER override the browser if the system Chrome is
# not the one you want to drive.

TAG=${1:-""}
BASE_URL=${BASE_URL:-""}
EXTRA=""
if [ -n "$BASE_URL" ]; then
    EXTRA="--variable BASE_URL:${BASE_URL}"
    echo "Targeting ${BASE_URL}"
fi
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="tests/results/${TIMESTAMP}"
mkdir -p ${OUTPUT_DIR}

if [ -n "$TAG" ]; then
    echo "Running tests with tag: ${TAG}"
    robot --include ${TAG} ${EXTRA} \
          --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
else
    echo "Running all tests"
    robot ${EXTRA} \
          --outputdir ${OUTPUT_DIR} \
          --log log.html \
          --report report.html \
          tests/
fi

echo ""
echo "Results saved to: ${OUTPUT_DIR}"
echo "Open ${OUTPUT_DIR}/report.html to view the test report."
