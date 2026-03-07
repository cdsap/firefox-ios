#!/bin/bash
# Run BrowserKit (Swift Package) tests, convert to JUnit XML, then import into Develocity
# Usage: ./run_browserkit_tests.sh [destination]
#
# Hook Point B: BrowserKit SPM unit tests -> JUnit XML -> Develocity Build Scan
#
# Note: BrowserKit depends on UIKit, so it must be built and tested using
# xcodebuild with an iOS simulator destination (not plain `swift test`).
#
# Examples:
#   ./run_browserkit_tests.sh
#   ./run_browserkit_tests.sh "platform=iOS Simulator,name=iPhone 16,OS=18.2"

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/test-reports"
BROWSERKIT_DIR="$SCRIPT_DIR/BrowserKit"
RESULT_BUNDLE="$SCRIPT_DIR/BrowserKitResults.xcresult"

DESTINATION="${1:-platform=iOS Simulator,name=iPhone 16,OS=18.2}"

echo "=== BrowserKit Test Pipeline ==="
echo "Destination: $DESTINATION"
echo ""

# Clean previous results
rm -rf "$RESULT_BUNDLE"
rm -f "$REPORTS_DIR"/browserkit-*.xml

# Step 1: Run BrowserKit tests via xcodebuild (UIKit requires iOS simulator)
echo "Step 1: Running xcodebuild test on BrowserKit package..."
xcodebuild test \
    -scheme BrowserKit \
    -destination "$DESTINATION" \
    -resultBundlePath "$RESULT_BUNDLE" \
    -packagePath "$BROWSERKIT_DIR" \
    CODE_SIGN_IDENTITY= CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO \
    2>&1 | tee "$SCRIPT_DIR/browserkit-test-raw.log"
TEST_EXIT=${PIPESTATUS[0]}

# Step 2: Convert to JUnit XML
echo ""
echo "Step 2: Converting to JUnit XML..."
python3 "$SCRIPT_DIR/xcresult_to_junit.py" \
    "$REPORTS_DIR/browserkit-tests.xml" \
    "$RESULT_BUNDLE" \
    "$SCRIPT_DIR/browserkit-test-raw.log"

# Step 3: Import into Develocity
echo ""
echo "Step 3: Importing into Develocity..."
"$SCRIPT_DIR/gradlew" import --no-configuration-cache 2>&1 || true

echo ""
echo "=== Pipeline complete ==="
echo "JUnit XML: $REPORTS_DIR/browserkit-tests.xml"
[ $TEST_EXIT -ne 0 ] && echo "Note: Some tests failed (exit code $TEST_EXIT)"
exit 0
