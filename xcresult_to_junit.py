#!/usr/bin/env python3
"""Convert .xcresult bundle or raw xcodebuild log to JUnit XML for Develocity import."""
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr


def extract_xcresult_json(xcresult_path):
    """Use xcresulttool to extract structured JSON from .xcresult bundle."""
    try:
        result = subprocess.run(
            ['xcrun', 'xcresulttool', 'get', '--path', xcresult_path, '--format', 'json', '--legacy'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def walk_action_tests(node, suite_name=''):
    """Recursively walk xcresulttool JSON to find test results."""
    tests = []
    node_type = node.get('_type', {}).get('_name', '')

    if node_type == 'ActionTestMetadata':
        name = node.get('name', {}).get('_value', 'unknown')
        duration = float(node.get('duration', {}).get('_value', 0))
        status = node.get('testStatus', {}).get('_value', 'Success')
        passed = status == 'Success'

        failure_output = ''
        summaries = node.get('failureSummaries', {}).get('_values', [])
        for s in summaries:
            msg = s.get('message', {}).get('_value', '')
            file_name = s.get('fileName', {}).get('_value', '')
            line = s.get('lineNumber', {}).get('_value', '')
            loc = f'{file_name}:{line}' if file_name else ''
            failure_output += f'{loc}: {msg}\n' if loc else f'{msg}\n'

        tests.append({
            'name': f'{suite_name}.{name}' if suite_name else name,
            'duration': duration,
            'passed': passed,
            'failure_output': failure_output.strip(),
        })
        return tests

    if node_type == 'ActionTestSummaryGroup':
        suite_name = node.get('name', {}).get('_value', suite_name)

    for key, value in node.items():
        if isinstance(value, dict):
            if '_values' in value:
                for item in value['_values']:
                    tests.extend(walk_action_tests(item, suite_name))
            else:
                tests.extend(walk_action_tests(value, suite_name))
    return tests


def parse_raw_log(log_path):
    """Fallback: parse raw xcodebuild console output for test results."""
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
        # Normalize ObjC bridged names: -[Module.Class method] -> Class.method
        nm = re.match(r'-\[(?:\w+\.)?(\w+)\s+(\w+)\]', raw_name)
        if nm:
            name = f'{nm.group(1)}.{nm.group(2)}'
        elif '.' in raw_name:
            name = raw_name
        else:
            name = raw_name

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


def to_junit_xml(tests, output_path, suite_name=None):
    """Write tests to JUnit XML format (Gradle-compatible)."""
    failures = sum(1 for t in tests if not t['passed'])
    total_time = round(sum(t['duration'] for t in tests), 3)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    hostname = escape(socket.gethostname())

    if not suite_name:
        classnames = sorted({t['name'].split('.')[0] for t in tests}) if tests else ['XCTests']
        suite_name = classnames[0] if len(classnames) == 1 else 'XCTestResults'

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
    lines.append(f'  <system-err>{cdata("")}</system-err>')
    lines.append('</testsuite>')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    if len(sys.argv) < 2:
        print('Usage: xcresult_to_junit.py <output.xml> [xcresult_path] [raw_log_path]', file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    xcresult_path = sys.argv[2] if len(sys.argv) > 2 else './TestResults.xcresult'
    raw_log_path = sys.argv[3] if len(sys.argv) > 3 else './raw-test.log'

    tests = []

    # Try xcresulttool first
    if os.path.isdir(xcresult_path):
        data = extract_xcresult_json(xcresult_path)
        if data:
            tests = walk_action_tests(data)
            if tests:
                print(f'Extracted {len(tests)} tests from {xcresult_path} via xcresulttool')

    # Fallback to raw log
    if not tests and os.path.isfile(raw_log_path):
        tests = parse_raw_log(raw_log_path)
        if tests:
            print(f'Parsed {len(tests)} tests from {raw_log_path} (raw log fallback)')

    if not tests:
        print('No test results found', file=sys.stderr)
        sys.exit(1)

    to_junit_xml(tests, output_path)
    print(f'Wrote JUnit XML to {output_path} ({len(tests)} tests)')


if __name__ == '__main__':
    main()
