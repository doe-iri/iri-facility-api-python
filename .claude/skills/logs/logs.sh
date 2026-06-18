#!/bin/bash
# name: logs
# description: Run dev server and capture logs to api.log

make dev 2>&1 | tee api.log
