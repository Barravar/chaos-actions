# Litmus Chaos Actions

[![CI](https://github.com/Barravar/chaos-actions/workflows/CI/badge.svg)](https://github.com/Barravar/chaos-actions/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/gh/Barravar/chaos-actions/branch/main/graph/badge.svg)](https://codecov.io/gh/Barravar/chaos-actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://github.com/Barravar/chaos-actions/blob/main/Dockerfile)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A GitHub Action for automating chaos engineering experiments using [Litmus Chaos](https://litmuschaos.io/) in Kubernetes environments. This action simplifies the integration of chaos testing into CI/CD pipelines by providing a streamlined interface to create and execute chaos experiments.

## Features

- 🚀 **Easy Integration**: Seamlessly integrate chaos experiments into GitHub workflows
- 🔄 **Flexible Execution**: Create new experiments or run existing ones
- 🔐 **Secure Authentication**: Built-in authentication with Litmus ChaosCenter
- 📊 **Comprehensive Logging**: Detailed logging with configurable log levels
- 🔁 **Retry Logic**: Automatic retry mechanism for transient failures
- ✅ **Type Safety**: Fully type-hinted Python codebase for better reliability

## Prerequisites

- A running [Litmus ChaosCenter](https://docs.litmuschaos.io/docs/getting-started/installation/) instance
- Kubernetes cluster with Litmus Chaos Infrastructure configured
- GitHub repository with appropriate permissions

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `LITMUS_URL` | URL of the Litmus ChaosCenter instance | Yes | - |
| `LITMUS_USERNAME` | Username for Litmus authentication | Yes | - |
| `LITMUS_PASSWORD` | Password for Litmus authentication | Yes | - |
| `LITMUS_PROJECT` | Name of the Litmus project | Yes | - |
| `LITMUS_ENVIRONMENT` | Name of the Litmus environment | Yes | - |
| `LITMUS_INFRA` | Name of the Chaos Infrastructure | Yes | - |
| `EXPERIMENT_MANIFEST` | YAML content or file path to experiment manifest | No* | `""` |
| `EXPERIMENT_NAME` | Name of existing experiment to run | No* | `""` |

\* Either `EXPERIMENT_MANIFEST` or `EXPERIMENT_NAME` must be provided.

## Environment Variables

The action supports additional configuration through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (`DEBUG` or `INFO`) | `INFO` |
| `HTTP_MAX_RETRIES` | Maximum number of HTTP retry attempts | `5` |
| `HTTP_BACKOFF_FACTOR` | Backoff factor for retries | `0.3` |
| `REQUEST_TIMEOUT` | Timeout for REST API requests (seconds) | `30` |
| `GRAPHQL_TIMEOUT` | Timeout for GraphQL requests (seconds) | `60` |
| `RUN_EXPERIMENT` | Whether to execute the experiment after creation | `true` |

## Outputs

This action produces the following outputs that can be used in subsequent workflow steps:

| Output | Description | Type | Example |
|--------|-------------|------|------|
| `EXPERIMENT_RESULT` | Overall experiment status | String | `Completed`, `Error`, `Stopped` |
| `RESILIENCY_SCORE` | Experiment resiliency score (0-100) | Number | `95.0` |
| `FAULT_RESULTS` | Detailed fault results in JSON format | JSON Array | See [Fault Results Schema](#fault-results-schema) |

### Fault Results Schema

The `FAULT_RESULTS` output contains an array of objects with the following structure:

```json
[
  {
    "fault_name": "pod-delete",
    "verdict": "Pass",
    "fail_step": "N/A",
    "probe_success_percentage": 100,
    "probes": [
      {
        "name": "check-app-status",
        "type": "httpProbe",
        "status": "Passed",
        "description": "Application is healthy and responding"
      }
    ]
  }
]
```

**Field Descriptions:**
- `fault_name`: Name of the chaos fault that was executed
- `verdict`: Pass/Fail/Awaited - the outcome of the fault injection
- `fail_step`: Step where the fault failed (if applicable), otherwise "N/A"
- `probe_success_percentage`: Percentage of successful probe checks
- `probes`: Array of probe results (optional, only if probes are configured)
  - `name`: Name of the probe
  - `type`: Type of probe (httpProbe, cmdProbe, k8sProbe, etc.)
  - `status`: Probe verdict (Passed/Failed)
  - `description`: Detailed message about the probe result (e.g., error messages, timeout details)

## Usage

### Basic Example

```yaml
name: Chaos Engineering Tests
on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:

jobs:
  chaos-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run Litmus Chaos Experiment
        id: chaos
        uses: Barravar/chaos-actions@v1
        with:
          LITMUS_URL: ${{ secrets.LITMUS_URL }}
          LITMUS_USERNAME: ${{ secrets.LITMUS_USERNAME }}
          LITMUS_PASSWORD: ${{ secrets.LITMUS_PASSWORD }}
          LITMUS_PROJECT: production
          LITMUS_ENVIRONMENT: prod-cluster
          LITMUS_INFRA: k8s-prod
          EXPERIMENT_NAME: pod-delete-demo

      - name: Check Experiment Results
        run: |
          echo "Experiment Status: ${{ steps.chaos.outputs.EXPERIMENT_RESULT }}"
          echo "Resiliency Score: ${{ steps.chaos.outputs.RESILIENCY_SCORE }}"
          echo "Fault Results: ${{ steps.chaos.outputs.FAULT_RESULTS }}"
```

### Creating a New Experiment from Manifest

```yaml
- name: Create and Run New Chaos Experiment
  uses: Barravar/chaos-actions@v1
  with:
    LITMUS_URL: https://chaos.example.com
    LITMUS_USERNAME: ${{ secrets.LITMUS_USERNAME }}
    LITMUS_PASSWORD: ${{ secrets.LITMUS_PASSWORD }}
    LITMUS_PROJECT: staging
    LITMUS_ENVIRONMENT: staging-cluster
    LITMUS_INFRA: k8s-staging
    EXPERIMENT_MANIFEST: |
      apiVersion: argoproj.io/v1alpha1
      kind: Workflow
      metadata:
        name: custom-pod-delete
        namespace: litmus
        annotations:
          description: Delete pods to test resilience
      spec:
        entrypoint: custom-chaos
        # ... rest of manifest
```

### Using Manifest from File

```yaml
- name: Run Chaos Experiment from File
  id: chaos-test
  uses: Barravar/chaos-actions@v1
  with:
    LITMUS_URL: ${{ secrets.LITMUS_URL }}
    LITMUS_USERNAME: ${{ secrets.LITMUS_USERNAME }}
    LITMUS_PASSWORD: ${{ secrets.LITMUS_PASSWORD }}
    LITMUS_PROJECT: dev
    LITMUS_ENVIRONMENT: dev-cluster
    LITMUS_INFRA: k8s-dev
    EXPERIMENT_MANIFEST: ./chaos-experiments/pod-delete.yaml
```

### Using Outputs for Quality Gates

You can use the outputs to enforce quality gates in your CI/CD pipeline:

```yaml
- name: Run Chaos Experiment
  id: chaos
  uses: Barravar/chaos-actions@v1
  with:
    LITMUS_URL: ${{ secrets.LITMUS_URL }}
    LITMUS_USERNAME: ${{ secrets.LITMUS_USERNAME }}
    LITMUS_PASSWORD: ${{ secrets.LITMUS_PASSWORD }}
    LITMUS_PROJECT: production
    LITMUS_ENVIRONMENT: prod-cluster
    LITMUS_INFRA: k8s-prod
    EXPERIMENT_NAME: comprehensive-chaos-suite

- name: Enforce Resiliency Threshold
  if: steps.chaos.outputs.RESILIENCY_SCORE < 80
  run: |
    echo "⚠️ Resiliency score ${{ steps.chaos.outputs.RESILIENCY_SCORE }} is below threshold (80)"
    exit 1

- name: Parse Fault Results
  run: |
    echo '${{ steps.chaos.outputs.FAULT_RESULTS }}' | jq '.[] | select(.verdict == "Fail")'

- name: Upload Results as Artifact
  uses: actions/upload-artifact@v4
  with:
    name: chaos-results
    path: |
      echo "Result: ${{ steps.chaos.outputs.EXPERIMENT_RESULT }}" > results.txt
      echo "Score: ${{ steps.chaos.outputs.RESILIENCY_SCORE }}" >> results.txt
      echo '${{ steps.chaos.outputs.FAULT_RESULTS }}' > faults.json
```

### Setting Custom Environment Variables

```yaml
- name: Run Chaos with Custom Config
  uses: Barravar/chaos-actions@v1
  env:
    LOG_LEVEL: DEBUG
    HTTP_MAX_RETRIES: 10
    REQUEST_TIMEOUT: 60
  with:
    # ... your inputs
```

### Creating Without Running

Create an experiment without immediately executing it:

```yaml
- name: Create Chaos Experiment Only
  uses: Barravar/chaos-actions@v1
  env:
    RUN_EXPERIMENT: false
  with:
    # ... your inputs
    EXPERIMENT_MANIFEST: ./experiments/network-chaos.yaml
```

## Project Structure

```
chaos-actions/
├── action.yaml                 # GitHub Action definition
├── Dockerfile                  # Container image definition
├── src/
│   ├── main.py                # Main entry point and orchestration
│   ├── client.py              # Litmus API client (REST + GraphQL)
│   ├── config.py              # Configuration and logger setup
│   ├── models/                # Data models
│   ├── services/              # Business logic (resources, experiments, monitoring)
│   └── utils/                 # Utilities (error handling, formatters, validation)
└── tests/                     # Comprehensive test suite (93% coverage)
```

## Architecture

The action is built using Python 3.11+ and runs in a lightweight Docker container (Python 3.12 Alpine) with a clean, service-oriented architecture:

### Core Components

- **main.py**: Entry point that orchestrates the complete workflow
  - Authenticates with Litmus ChaosCenter
  - Resolves resource IDs (project, environment, infrastructure)
  - Creates or retrieves chaos experiments
  - Executes experiments and monitors completion
  - Injectable configuration for testing

- **client.py**: HTTP client with retry logic for REST and GraphQL APIs
  - Context manager for resource cleanup
  - Automatic authentication and token management
  - Configurable timeouts and retry strategies
  - Sensitive data redaction in logs

- **services/**: Business logic layer with focused responsibilities
  - **resources.py**: ID resolution for projects, environments, and infrastructure
  - **experiments.py**: Experiment creation and execution
  - **monitoring.py**: Status polling with exponential backoff and timeout handling

- **utils/**: Cross-cutting utilities
  - **error_handler.py**: Decorator-based error handling (`@handle_graphql_errors`, `@handle_rest_errors`)
  - **formatters.py**: Result formatting and logging
  - **github_outputs.py**: GitHub Actions output generation and fault result extraction
  - **manifest.py**: YAML validation and JSON serialization
  - **serializers.py**: Data serialization utilities

- **models/**: Type-safe data models using dataclasses
  - Experiment request models
  - Clean separation of domain models

### Code Quality

- ✅ **93% Test Coverage**: Comprehensive test suite with 180 passing tests
- ✅ **CI/CD Pipeline**: Automated testing on Python 3.11 and 3.12 via GitHub Actions
- ✅ **Coverage Tracking**: Integration with Codecov for coverage monitoring
- ✅ **Type Safety**: Full type hints with modern Python 3.11+ syntax (`dict[str, Any]`, `str | None`)
- ✅ **Service-Oriented**: Clear separation of concerns with dedicated service modules
- ✅ **Pre-commit Hooks**: Automated code quality checks (black, isort, flake8, mypy, bandit)
- ✅ **Security**: Bandit security scanning, password masking, secret redaction in logs
- ✅ **DRY Principle**: Decorators and helper functions eliminate code duplication
- ✅ **Constants**: All magic numbers extracted to named constants
- ✅ **Documentation**: Comprehensive docstrings with Args/Returns/Raises
- ✅ **Docker Best Practices**: Multi-stage builds, non-root user, minimal Alpine base image

## Security

### Security Features

- **Credential Protection**: Passwords and tokens are redacted from logs
- **Bandit Security Scanning**: Automated security vulnerability detection in CI
- **Non-root Container**: Docker container runs as non-privileged user (UID 1000)
- **Minimal Attack Surface**: Alpine Linux base with only required dependencies
- **Secret Management**: Supports GitHub Actions secrets for credential storage

### Reporting Vulnerabilities

If you discover a security vulnerability, please email **barravar@barravar.com.br**. Please do not use public issue tracker for security issues.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). For available versions, see the [releases page](https://github.com/Barravar/chaos-actions/releases).

**Usage Recommendations:**
- Production: Use specific version tags (e.g., `@v1.0.0`)
- Development: Use major version tags (e.g., `@v1`) for latest compatible version
- Testing: Use `@main` for cutting edge (not recommended for production)

## Contributing

Contributions are welcome! For development setup, testing guidelines, and code quality standards, please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See the repository for details.

## Acknowledgments

- Built with [Litmus Chaos](https://litmuschaos.io/)
- Inspired by the chaos engineering community
- Thanks to all [contributors](https://github.com/Barravar/chaos-actions/graphs/contributors)
- Developed with AI assistance (GitHub Copilot and Claude) for code quality, testing, and documentation

## Support and Resources

- 📚 [Litmus Documentation](https://docs.litmuschaos.io/)
- 🐛 [Report Issues](https://github.com/Barravar/chaos-actions/issues)
- 💬 [Discussions](https://github.com/Barravar/chaos-actions/discussions)
- 🔧 [Contributing Guide](CONTRIBUTING.md)
- 📦 [Release Notes](https://github.com/Barravar/chaos-actions/releases)

---

**Copyright © 2026 Barravar Inc.**
**Maintainer**: Barravar Inc. <barravar@barravar.com.br>
**Repository**: [github.com/Barravar/chaos-actions](https://github.com/Barravar/chaos-actions)
**License**: MIT
