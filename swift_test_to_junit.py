#!/usr/bin/env python3
"""Convert `swift test` console output to JUnit XML for Develocity import."""
import re
import socket
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr


def normalize_test_name(raw_name):
    """Normalize ObjC-bridged or Swift test names to 'ClassName.methodName'.

    Input formats:
      '-[ModuleTests.ClassName testMethodName]'  -> 'ClassName.testMethodName'
      'ClassName.testMethodName'                  -> 'ClassName.testMethodName'
    """
    m = re.match(r'-\[(?:\w+\.)?(\w+)\s+(\w+)\]', raw_name)
    if m:
        return f'{m.group(1)}.{m.group(2)}'
    if '.' in raw_name:
        return raw_name
    return raw_name


def parse_swift_test_log(log_path):
    """Parse raw `swift test` output for test results."""
    with open(log_path, encoding='utf-8', errors='replace') as f:
        log = f.read()

    tests = []
    pattern = (
        r"Test [Cc]ase '([^']+)' (passed|failed)"
        r"(?: on '[^']+')?"
        r" \((\d+\.?\d*) seconds\)"
    )
    matches = list(re.finditer(pattern, log))

    seen = set()
    for i, m in enumerate(matches):
        raw_name, status, duration = m.groups()
        name = normalize_test_name(raw_name)
        if name in seen:
            continue
        seen.add(name)

        failure_output = ''
        if status == 'failed':
            start = max(0, m.start() - 500)
            end = matches[i + 1].start() if i + 1 < len(matches) else min(m.end() + 2000, len(log))
            chunk = log[start:end]
            fail_lines = [
                line.strip() for line in chunk.split('\n')
                if line.strip() and (
                    'error:' in line.lower() or 'XCTAssert' in line
                    or 'failed' in line.lower() or '.swift:' in line
                )
            ]
            failure_output = '\n'.join(fail_lines) if fail_lines else ''

        tests.append({
            'name': name,
            'duration': float(duration),
            'passed': status == 'passed',
            'failure_output': failure_output,
        })

    return tests


def cdata(text):
    return '<![CDATA[' + text.replace(']]>', ']]]]><![CDATA[>') + ']]>'


def to_junit_xml(tests, output_path, suite_name=None, raw_log=''):
    """Write tests to JUnit XML format (Gradle-compatible)."""
    failures = sum(1 for t in tests if not t['passed'])
    total_time = round(sum(t['duration'] for t in tests), 3)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    hostname = escape(socket.gethostname())

    if not suite_name:
        classnames = sorted({t['name'].split('.')[0] for t in tests}) if tests else ['SwiftTests']
        suite_name = classnames[0] if len(classnames) == 1 else 'BrowserKitTests'

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="{escape(suite_name)}" tests="{len(tests)}" skipped="0" failures="{failures}"'
        f' errors="0" timestamp="{timestamp}" hostname="{hostname}" time="{total_time}">',
        '  <properties/>',
    ]

    for t in tests:
        classname = t['name'].split('.')[0] if '.' in t['name'] else suite_name
        method = t['name'].split('.', 1)[-1].rstrip('()')
        line = f'  <testcase name={quoteattr(method)} classname={quoteattr(classname)} time="{t["duration"]:.3f}"'
        if t['passed']:
            lines.append(line + '/>')
        else:
            msg = (t.get('failure_output') or 'Test failed').strip()[:5000]
            lines.append(line + '>')
            lines.append(f'    <failure message={quoteattr(msg[:500])}>{escape(msg)}</failure>')
            lines.append('  </testcase>')

    lines.append(f'  <system-out>{cdata("")}</system-out>')
    err_content = raw_log if raw_log and failures > 0 else ''
    lines.append(f'  <system-err>{cdata(err_content)}</system-err>')
    lines.append('</testsuite>')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    if len(sys.argv) < 2:
        print('Usage: swift_test_to_junit.py <log_file> [output.xml] [suite_name]', file=sys.stderr)
        sys.exit(1)

    log_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'test-report.xml'
    suite_name = sys.argv[3] if len(sys.argv) > 3 else None

    tests = parse_swift_test_log(log_path)
    if not tests:
        print(f'No test results found in {log_path}', file=sys.stderr)
        sys.exit(1)

    raw_log = ''
    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            raw_log = f.read()
    except OSError:
        pass

    to_junit_xml(tests, output_path, suite_name, raw_log)
    print(f"Wrote JUnit XML to {output_path} ({len(tests)} tests)")


if __name__ == '__main__':
    main()


