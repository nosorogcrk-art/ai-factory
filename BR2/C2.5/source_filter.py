#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
source_filter.py – базовый модуль фильтра качества источников.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple

logger = logging.getLogger(__name__)

def check_source(source_data: dict) -> Tuple[bool, str]:
    """
    Проверяет источник на соответствие критериям качества.
    Возвращает (allowed: bool, reason: str).
    """
    source_type = source_data.get("type")
    if not source_type:
        return False, "missing source type"

    if source_type == "github":
        stars = source_data.get("stars", 0)
        last_commit = source_data.get("last_commit")
        has_tests = source_data.get("has_tests", False)
        license_name = source_data.get("license")

        if stars < 100:
            return False, f"stars below threshold (required 100, got {stars})"
        if last_commit:
            try:
                commit_date = datetime.fromisoformat(last_commit)
                if datetime.now() - commit_date > timedelta(days=365):
                    return False, f"last commit older than 1 year ({last_commit})"
            except:
                pass
        if not has_tests:
            return False, "no tests"
        allowed_licenses = ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC"]
        if license_name not in allowed_licenses:
            return False, f"license '{license_name}' not allowed"
        return True, ""

    elif source_type == "arxiv":
        published_date = source_data.get("published_date")
        category = source_data.get("category")

        if published_date:
            try:
                pub_date = datetime.fromisoformat(published_date)
                if datetime.now() - pub_date > timedelta(days=730):
                    return False, f"published more than 2 years ago ({published_date})"
            except:
                pass
        allowed_categories = ["cs.AI", "cs.LG", "cs.CL", "stat.ML"]
        if category not in allowed_categories:
            return False, f"category '{category}' not allowed"
        return True, ""

    elif source_type == "blog":
        published_date = source_data.get("published_date")
        domain = source_data.get("domain")

        if published_date:
            try:
                pub_date = datetime.fromisoformat(published_date)
                if datetime.now() - pub_date > timedelta(days=365):
                    return False, f"published more than 1 year ago ({published_date})"
            except:
                pass
        trusted_domains = ["medium.com", "dev.to", "habr.com", "opensource.com"]
        if domain not in trusted_domains:
            return False, f"domain '{domain}' not trusted"
        return True, ""

    else:
        return False, f"unknown source type '{source_type}'"
