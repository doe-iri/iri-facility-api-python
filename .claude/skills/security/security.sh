#!/bin/bash
# name: security
# description: Run security scans (pip-audit and bandit)

make audit && make bandit
