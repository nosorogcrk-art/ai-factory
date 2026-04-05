#!/usr/bin/env python3
from source_filter import check_source

test_cases = [
    ({"type": "github", "stars": 150, "last_commit": "2025-01-01T00:00:00Z", "has_tests": True, "license": "MIT"}, True),
    ({"type": "github", "stars": 50, "last_commit": "2025-01-01T00:00:00Z", "has_tests": True, "license": "MIT"}, False),
    ({"type": "arxiv", "published_date": "2024-01-01T00:00:00Z", "category": "cs.AI"}, True),
    ({"type": "blog", "published_date": "2026-01-01T00:00:00Z", "domain": "medium.com"}, True),
]

for data, expected in test_cases:
    result, reason = check_source(data)
    assert result == expected, f"Failed for {data}: got {result}, expected {expected}"
print("All tests passed.")
