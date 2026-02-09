# Lint Skill

Run full validation suite (format, ruff, pylint, audit, bandit)

## Description

This skill runs a comprehensive validation suite on the codebase, including formatting, linting, and security checks.

## Usage

```bash
/lint
```

## What it does

- Runs `make lint` which executes:
  - Code formatting checks
  - Ruff linting
  - Pylint analysis
  - Pip-audit for dependency vulnerabilities
  - Bandit security scanning

This is the full pre-commit validation suite to ensure code quality and security before merging changes.
