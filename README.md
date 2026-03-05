# Litmus Chaos Actions

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
        uses: Barravar/chaos-actions@v1
        with:
          LITMUS_URL: ${{ secrets.LITMUS_URL }}
          LITMUS_USERNAME: ${{ secrets.LITMUS_USERNAME }}
          LITMUS_PASSWORD: ${{ secrets.LITMUS_PASSWORD }}
          LITMUS_PROJECT: production
          LITMUS_ENVIRONMENT: prod-cluster
          LITMUS_INFRA: k8s-prod
          EXPERIMENT_NAME: pod-delete-demo
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
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── pyproject.toml              # Python project metadata and tool configs
├── .pre-commit-config.yaml     # Pre-commit hooks configuration
├── .flake8                     # Flake8 linting configuration
├── src/
│   ├── __init__.py
│   ├── main.py                # Main entry point and orchestration
│   ├── client.py              # Litmus API client (REST + GraphQL)
│   ├── config.py              # Configuration and logger setup
│   ├── exceptions.py          # Custom exception classes
│   ├── litmus_types.py        # Type definitions (TypedDict, Enum)
│   ├── queries.py             # GraphQL query definitions
│   ├── models/                # Data models for API requests
│   │   ├── __init__.py
│   │   └── experiment.py      # Experiment request models
│   ├── services/              # Business logic layer
│   │   ├── __init__.py
│   │   ├── resources.py       # ID resolution (project, env, infra)
│   │   ├── experiments.py     # Experiment creation and execution
│   │   └── monitoring.py      # Status polling and monitoring
│   └── utils/                 # Utility modules
│       ├── __init__.py
│       ├── error_handler.py   # Error handling decorators
│       ├── formatters.py      # Output formatting utilities
│       ├── manifest.py        # Manifest validation and processing
│       └── serializers.py     # JSON serialization utilities
└── tests/
    ├── conftest.py            # Pytest fixtures and configuration
    ├── test_main.py           # Legacy main tests
    ├── test_main_integration.py  # Integration tests for main.py
    ├── test_client.py         # Client tests
    ├── test_monitoring.py     # Monitoring service tests
    ├── test_formatters.py     # Formatter tests
    └── test_error_handler.py  # Error handler tests
```

## Architecture

The action is built using Python 3.11+ and runs in a Docker container with a clean, service-oriented architecture:

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
  - **manifest.py**: YAML validation and JSON serialization
  - **serializers.py**: Data serialization utilities

- **models/**: Type-safe data models using dataclasses
  - Experiment request models
  - Clean separation of domain models

### Code Quality

- ✅ **93% Test Coverage**: Comprehensive test suite with 158 passing tests
- ✅ **Type Safety**: Full type hints with modern Python 3.11+ syntax (`dict[str, Any]`, `str | None`)
- ✅ **Service-Oriented**: Clear separation of concerns with dedicated service modules
- ✅ **Pre-commit Hooks**: Automated code quality checks (black, isort, flake8, mypy, bandit)
- ✅ **Security**: Bandit security scanning, password masking, secret redaction
- ✅ **DRY Principle**: Decorators and helper functions eliminate code duplication
- ✅ **Constants**: All magic numbers extracted to named constants
- ✅ **Documentation**: Comprehensive docstrings with Args/Returns/Raises

## Troubleshooting

### Common Issues

**Problem**: `Environment X not found`
- Verify the environment name matches exactly (case-sensitive)
- Ensure the environment exists in the specified project
- Check user permissions for the project

**Problem**: `Chaos Infrastructure is not active`
- Verify the chaos infrastructure agent is running in your cluster
- Check agent logs: `kubectl logs -n litmus -l app=chaos-exporter`
- Confirm infrastructure is connected in Litmus UI

**Problem**: `Invalid YAML manifest`
- Validate YAML syntax using a linter
- Ensure the manifest follows Argo Workflow specifications
- Check for required metadata fields (name, namespace, annotations.description)

**Problem**: HTTP timeout errors
- Increase `REQUEST_TIMEOUT` or `GRAPHQL_TIMEOUT` environment variables
- Check network connectivity to Litmus instance
- Verify Litmus instance is responsive

## Contributing

Contributions are welcome! For development setup, testing guidelines, and code quality standards, please see [CONTRIBUTING.md](CONTRIBUTING.md).

## AI Development Disclaimer

This project was developed with the assistance of AI tools (GitHub Copilot and Claude) to enhance code quality, test coverage, and documentation. While AI assisted in:
- Code review and recommendations
- Test suite expansion (86% → 93% coverage)
- Implementation of pre-commit hooks and linting
- Documentation improvements

All code has been reviewed, tested, and validated by human developers to ensure correctness, security, and adherence to best practices.

## Acknowledgments

- Built with [Litmus Chaos](https://litmuschaos.io/)
- Inspired by the chaos engineering community
- Thanks to all contributors
- AI-assisted development with GitHub Copilot and Claude

## Support

- 📚 [Litmus Documentation](https://docs.litmuschaos.io/)
- 🐛 [Report Issues](https://github.com/Barravar/chaos-actions/issues)
- 💬 [Discussions](https://github.com/Barravar/chaos-actions/discussions)

---

**Maintainer**: Barravar Inc. <barravar@barravar.com.br>
**Repository**: [github.com/Barravar/chaos-actions](https://github.com/Barravar/chaos-actions)
