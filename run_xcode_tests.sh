#!/bin/bash
# Run Firefox iOS Xcode tests, convert to JUnit XML, then import into Develocity
# Usage: ./run_xcode_tests.sh [scheme] [test_plan]
#
# Hook Point A: xcodebuild test -> .xcresult -> JUnit XML -> Develocity Build Scan
#
# Examples:
#   ./run_xcode_tests.sh                          # Fennec scheme, all tests
#   ./run_xcode_tests.sh Fennec Smoketest1         # Fennec scheme, Smoketest1 plan
#   ./run_xcode_tests.sh Firefox                   # Firefox scheme, all tests

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/test-reports"
XCODEPROJ="$SCRIPT_DIR/firefox-ios/Client.xcodeproj"

SCHEME="${1:-Fennec}"
TEST_PLAN="${2:-}"
RESULT_BUNDLE="$SCRIPT_DIR/TestResults.xcresult"

echo "=== Firefox iOS Xcode Test Pipeline ==="
echo "Scheme:    $SCHEME"
echo "Test Plan: ${TEST_PLAN:-all}"
echo ""

# Clean previous results
rm -rf "$RESULT_BUNDLE"
rm -f "$REPORTS_DIR"/xcode-*.xml

# Step 1: Run xcodebuild test
echo "Step 1: Running xcodebuild test..."
TEST_PLAN_ARG=""
[ -n "$TEST_PLAN" ] && TEST_PLAN_ARG="-testPlan $TEST_PLAN"

xcodebuild test \
    -project "$XCODEPROJ" \
    -scheme "$SCHEME" \
    -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.2' \
    -resultBundlePath "$RESULT_BUNDLE" \
    $TEST_PLAN_ARG \
    CODE_SIGN_IDENTITY= CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO \
    2>&1 | tee "$SCRIPT_DIR/xcode-test-raw.log"
TEST_EXIT=${PIPESTATUS[0]}

# Step 2: Convert to JUnit XML
echo ""
echo "Step 2: Converting to JUnit XML..."
python3 "$SCRIPT_DIR/xcresult_to_junit.py" \
    "$REPORTS_DIR/xcode-tests.xml" \
    "$RESULT_BUNDLE" \
    "$SCRIPT_DIR/xcode-test-raw.log"

# Step 3: Import into Develocity
echo ""
echo "Step 3: Importing into Develocity..."
"$SCRIPT_DIR/gradlew" import --no-configuration-cache 2>&1 || true

echo ""
echo "=== Pipeline complete ==="
echo "JUnit XML: $REPORTS_DIR/xcode-tests.xml"
[ $TEST_EXIT -ne 0 ] && echo "Note: Some tests failed (exit code $TEST_EXIT)"
exit 0
