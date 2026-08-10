# Security Skill

Run security scans (pip-audit and bandit)

## Description

This skill performs security scanning on the codebase and dependencies to identify potential vulnerabilities.

## Usage

```bash
/security
```

## What it does

- Runs `make audit` to check for known vulnerabilities in Python dependencies using pip-audit
- Runs `make bandit` to scan code for common security issues

Use this regularly to ensure the codebase doesn't have known security vulnerabilities or insecure code patterns.
