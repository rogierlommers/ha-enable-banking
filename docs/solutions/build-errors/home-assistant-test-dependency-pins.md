---
title: Keep Home Assistant test dependencies on one compatible release set
date: 2026-11-14
last_updated: 2026-11-14
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
environment. PR #26 corrected those pins for Python 3.13, but Dependabot then
could not remediate Home Assistant security alerts: every patched Home Assistant
release required Python 3.14.2 or newer.

## Symptoms

- `pip install -e '.[test]'` reports `ResolutionImpossible`.
- Resolving one conflict exposes another before lint or pytest can start.
- Dependabot reports `security_update_not_possible` even though a patched Home
  Assistant release exists.

## What Didn't Work

- Upgrading PyJWT to 2.15.1 conflicted with Home Assistant 2026.2.3, which
  requires PyJWT 2.10.1.
- Keeping that PyJWT version but accepting every other Dependabot proposal
  still failed because `pytest-homeassistant-custom-component==0.13.316`
  requires pytest 9.0.0, pytest-aiohttp 1.1.0, and pytest-cov 7.0.0.
- Keeping the project on Python 3.13 limited Home Assistant to 2026.2.3. The
  first release that fixes every open Home Assistant alert is 2026.7.0, which
  requires Python 3.14.2 or newer.

## Solution

Treat Python and the Home Assistant test stack as a coordinated release set.
Use a current `pytest-homeassistant-custom-component` release and copy its exact
Home Assistant and pytest-family requirements:

```toml
dependencies = [
  "PyJWT[crypto]==2.15.1",
]

test = [
  "homeassistant==2026.10.4",
  "pytest==9.0.3",
  "pytest-aiohttp==1.1.1",
  "pytest-homeassistant-custom-component==0.13.375",
  "pytest-cov==7.1.0",
  "ruff==0.17.4",
]
```

Set the project and CI minimum to Python 3.14.2, then verify the complete extra
before evaluating individual lint or test failures:

```bash
pip install -e '.[test]'
ruff check custom_components tests
pytest
```

## Why This Works

`pytest-homeassistant-custom-component` mirrors a specific Home Assistant test
environment and pins several pytest plugins exactly. Resolving all direct
requirements together preserves that tested combination instead of selecting
newer versions that satisfy Dependabot individually but cannot coexist. The
project's minimum Python version also controls which Home Assistant security
updates Dependabot considers installable.

## Prevention

- For grouped dependency PRs, run a clean dependency resolution using the same
  Python version as CI before accepting individual version proposals.
- When the resolver reports a conflict, inspect every exact requirement from
  Home Assistant and `pytest-homeassistant-custom-component`; the first error
  may hide additional incompatible updates.
- When Dependabot reports `security_update_not_possible`, compare the patched
  dependency's Python requirement with both `requires-python` and the CI Python
  version.

## Related Issues

- GitHub PR #20 exposed the incompatible grouped update.
- GitHub PR #26 exposed the Python-version security-update ceiling.
