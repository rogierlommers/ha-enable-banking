---
title: Keep Home Assistant test dependencies on one compatible release set
date: 2026-11-14
category: build-errors
module: Python test dependencies
problem_type: build_error
component: testing_framework
symptoms:
  - pip reports ResolutionImpossible before lint or tests can run
  - A grouped Dependabot update changes packages that the Home Assistant test helper pins exactly
root_cause: config_error
resolution_type: dependency_update
severity: high
tags: [home-assistant, pytest, dependencies, dependabot, ci]
---

# Keep Home Assistant test dependencies on one compatible release set

## Problem

PR #20 grouped independent Python updates and produced an unsatisfiable test
environment. Upgrading Home Assistant and its custom-component test helper at
the same time also upgraded packages that those releases still pinned to older
exact versions, so CI stopped during installation.

## Symptoms

- `pip install -e '.[test]'` reports `ResolutionImpossible`.
- Resolving one conflict exposes another before lint or pytest can start.

## What Didn't Work

- Upgrading PyJWT to 2.15.1 conflicted with Home Assistant 2026.2.3, which
  requires PyJWT 2.10.1.
- Keeping that PyJWT version but accepting every other Dependabot proposal
  still failed because `pytest-homeassistant-custom-component==0.13.316`
  requires pytest 9.0.0, pytest-aiohttp 1.1.0, and pytest-cov 7.0.0.

## Solution

Treat the Home Assistant test stack as a coordinated release set. For the
Home Assistant 2026.2.3 test environment, use:

```toml
dependencies = [
  "PyJWT[crypto]==2.10.1,<3",
]

test = [
  "homeassistant==2026.2.3",
  "pytest==9.0.0",
  "pytest-aiohttp==1.1.0",
  "pytest-homeassistant-custom-component==0.13.316",
  "pytest-cov==7.0.0",
  "ruff==0.17.4",
]
```

Verify the complete extra with Python 3.13 before evaluating individual lint or
test failures:

```bash
pip install -e '.[test]'
ruff check custom_components tests
pytest
```

## Why This Works

`pytest-homeassistant-custom-component` mirrors a specific Home Assistant test
environment and pins several pytest plugins exactly. Resolving all direct
requirements together preserves that tested combination instead of selecting
newer versions that satisfy Dependabot individually but cannot coexist.

## Prevention

- For grouped dependency PRs, run a clean Python 3.13 dependency resolution
  before accepting individual version proposals.
- When the resolver reports a conflict, inspect every exact requirement from
  Home Assistant and `pytest-homeassistant-custom-component`; the first error
  may hide additional incompatible updates.

## Related Issues

- GitHub PR #20 exposed the incompatible grouped update.
