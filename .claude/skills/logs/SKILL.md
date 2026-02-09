# Logs Skill

Run dev server and capture logs to api.log

## Description

This skill starts the development server and captures all output (stdout and stderr) to a log file for review.

## Usage

```bash
/logs
```

## What it does

- Runs `make dev` to start the development server
- Captures all output to `api.log` file
- Displays output in real-time while also saving to file

Useful for debugging issues by having a persistent log file to review after the server runs.
