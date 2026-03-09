#!/usr/bin/env python3
"""
Add required 'timestamp' attribute to JUnit XML testsuite elements.
Develocity/Gradle ImportJUnitXmlReports requires this attribute.
xcpretty does not include it by default.
"""
import glob
import re
import sys
from datetime import datetime, timezone


def fix_junit_timestamp(file_path):
    """Add timestamp attribute to testsuite element if missing."""
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    # Match <testsuite ...> and add timestamp before the closing > if missing
    def add_timestamp(match):
        tag = match.group(0)
        if 'timestamp=' in tag:
            return tag
        # Insert timestamp before >
        return tag[:-1] + f' timestamp="{timestamp}">'

    new_content = re.sub(r'<testsuite[^>]*>', add_timestamp, content)
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print('Usage: fix_junit_timestamp.py <file.xml> [file2.xml ...]', file=sys.stderr)
        sys.exit(1)

    fixed = 0
    for pattern in sys.argv[1:]:
        for path in sorted(glob.glob(pattern)):
            if fix_junit_timestamp(path):
                print(f'Added timestamp to {path}')
                fixed += 1

    if fixed:
        print(f'Fixed {fixed} file(s)')


if __name__ == '__main__':
    main()
