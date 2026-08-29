# Check Skill

Quick format and ruff linting check

## Description

This skill runs a quick validation check on the codebase by formatting code and running ruff linter.

## Usage

```bash
/check
```

## What it does

- Runs `make format` to format code
- Runs `make ruff` for linting checks

This is a fast validation step useful before committing changes.
