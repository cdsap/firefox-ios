#!/bin/bash
# Import pre-existing JUnit XML files into Develocity
# Usage: ./import_existing_junit.sh <junit-file-or-glob> [...]
#
# This is for CI environments where JUnit XML is already produced
# (e.g. by xcpretty -r junit) and just needs to be imported into Develocity.
#
# Examples:
#   ./import_existing_junit.sh firefox-ios/combined.xml
#   ./import_existing_junit.sh firefox-ios/junit-smoketest*.xml
#   ./import_existing_junit.sh focus-ios/junit-*.xml

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/test-reports"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <junit-xml-file> [...]" >&2
    exit 1
fi

# Clean previous reports
rm -f "$REPORTS_DIR"/*.xml

# Copy provided JUnit XML files into the reports directory
COUNT=0
for f in "$@"; do
    if [ -f "$f" ]; then
        BASENAME=$(basename "$f")
        cp "$f" "$REPORTS_DIR/$BASENAME"
        echo "Copied: $f -> test-reports/$BASENAME"
        COUNT=$((COUNT + 1))
    else
        echo "Warning: $f not found, skipping" >&2
    fi
done

if [ $COUNT -eq 0 ]; then
    echo "No JUnit XML files found" >&2
    exit 1
fi

echo ""
echo "Importing $COUNT JUnit XML file(s) into Develocity..."
"$SCRIPT_DIR/gradlew" import --no-configuration-cache 2>&1

echo ""
echo "=== Import complete ==="
