#!/usr/bin/env python3
"""
Fix JUnit XML for Develocity/Gradle ImportJUnitXmlReports compatibility:
- Add 'timestamp' attribute to testsuite elements (xcpretty omits it)
- Add 'time' attribute to testcase elements (Gradle parser NPE when missing on failed tests)
"""
import glob
import re
import sys
from datetime import datetime, timezone


def fix_junit_xml(file_path):
    """Add required attributes to JUnit XML for Gradle import."""
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    # 1. Add timestamp to <testsuite ...> if missing
    def add_timestamp(match):
        tag = match.group(0)
        if 'timestamp=' in tag:
            return tag
        return tag[:-1] + f' timestamp="{timestamp}">'

    new_content = re.sub(r'<testsuite[^>]*>', add_timestamp, content)

    # 2. Add time="0" to <testcase ...> or <testcase .../> if missing (Gradle parser NPE when absent)
    def add_time(match):
        tag = match.group(0)
        if ' time=' in tag or " time='" in tag:
            return tag
        # Handle self-closing <testcase .../> and opening <testcase ...>
        if tag.endswith('/>'):
            return tag[:-2] + ' time="0"/>'
        return tag[:-1] + ' time="0">'

    new_content = re.sub(r'<testcase[^>]*(?:>|/>)', add_time, new_content)

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
            if fix_junit_xml(path):
                print(f'Fixed JUnit XML: {path}')
                fixed += 1

    if fixed:
        print(f'Fixed {fixed} file(s)')


if __name__ == '__main__':
    main()
