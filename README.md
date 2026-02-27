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

## Advanced Configuration

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
├── action.yaml                # GitHub Action definition
├── Dockerfile                 # Container image definition
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Pytest configuration
├── pyproject.toml             # Python project metadata
├── src/
│   ├── main.py               # Main entry point and orchestration
│   ├── client.py             # Litmus API client (REST + GraphQL)
│   ├── config.py             # Configuration and logger setup
│   ├── exceptions.py         # Custom exception classes
│   ├── models/               # Data models for API requests
│   │   ├── __init__.py
│   │   └── experiment.py
│   ├── queries.py            # GraphQL query definitions
│   ├── litmus_types.py       # Type definitions
│   └── utils/                # Utility modules
│       ├── __init__.py
│       ├── error_handler.py  # Error handling decorators
│       ├── manifest.py       # Manifest validation and I/O
│       └── serializers.py    # JSON serialization utilities
└── tests/
    └── test_main.py          # Comprehensive unit tests (548 lines)
```

## Architecture

The action is built using Python 3.10+ and runs in a Docker container with a modular, well-tested architecture:

### Core Components

- **main.py (791 lines)**: Orchestrates the complete workflow
  - ID resolution (project, environment, infrastructure)
  - Experiment creation and execution
  - Status monitoring with exponential backoff
  - Result formatting and logging

- **LitmusClient**: HTTP client with retry logic for REST and GraphQL APIs
  - Context manager for resource cleanup
  - Automatic token refresh
  - Configurable timeouts and retries

- **Error Handling Decorators**: DRY error handling via `@handle_graphql_errors` and `@handle_rest_errors`
  - Wraps 6 functions for consistent error reporting
  - Context-aware error messages

- **Manifest Processing**:
  - YAML validation with structure checks
  - Metadata extraction and normalization
  - Compact JSON serialization for API

- **Configuration**: Injectable config for testing
  - Environment variable loading
  - Type-safe dataclasses
  - Retry configuration

### Code Quality

- ✅ **Type Safety**: Full type hints with Python 3.10+ syntax
- ✅ **Tested**: 548 lines of tests with 17 test classes
- ✅ **Modular**: Functions refactored to single responsibility
- ✅ **Constants**: All magic numbers extracted to named constants
- ✅ **DRY**: Helper functions and decorators eliminate duplication

## Development

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Barravar/chaos-actions.git
   cd chaos-actions
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Tests

The project includes comprehensive unit tests (548 lines, 17 test classes):

```bash
# Run all tests
pytest tests/test_main.py -v

# Run with coverage report
pytest tests/test_main.py --cov=src --cov-report=html

# Run specific test class
pytest tests/test_main.py::TestCreateChaosExperiment -v

# Run with debug output
pytest tests/test_main.py -v -s
```

Test coverage includes:
- ID resolution functions (project, environment, infrastructure)
- Experiment creation and execution
- Helper functions (manifest parsing, JSON serialization)
- Error handling and edge cases
- Decorator functionality

### Local Testing with Real Litmus Instance

1. Set environment variables:
   ```bash
   export LITMUS_URL="https://chaos.example.com"
   export LITMUS_USERNAME="admin"
   export LITMUS_PASSWORD="your-password"
   export LITMUS_PROJECT="test-project"
   export LITMUS_ENVIRONMENT="test-env"
   export LITMUS_INFRA="test-infra"
   export EXPERIMENT_NAME="test-experiment"
   export LOG_LEVEL="DEBUG"
   ```

2. Run the script:
   ```bash
   python3 -m src.main
   ```

### Building the Docker Image

```bash
docker build -t chaos-actions:dev .
docker run --env-file .vars chaos-actions:dev
```

### Code Quality Checks

```bash
# Type checking (if mypy installed)
mypy src/

# Linting
flake8 src/ --max-line-length=120

# Format check
black --check src/
```

## Error Handling

The action provides detailed error messages for common issues:

- **Authentication Failures**: Invalid credentials or unreachable Litmus instance
- **Missing Resources**: Project, environment, or infrastructure not found
- **Invalid Manifests**: YAML parsing errors or invalid experiment definitions
- **Infrastructure Issues**: Inactive or unconfirmed chaos infrastructure
- **API Errors**: Network timeouts, rate limiting, or server errors

All errors are logged with context to help troubleshooting.

## Security Considerations

- **Credentials**: Always store Litmus credentials in GitHub Secrets, never in code
- **Permissions**: Use least-privilege service accounts for Litmus authentication
- **Manifest Validation**: Ensure experiment manifests are reviewed before execution
- **Network Security**: Use HTTPS for all Litmus API communications
- **Audit Logs**: Monitor Litmus audit logs for unauthorized chaos experiments

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

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and returns (Python 3.10+ syntax with `|` for unions)
- Add docstrings for all public functions and classes (Google style)
- Keep functions focused and modular (single responsibility principle)
- Prefix private/internal functions with `_`
- Extract magic numbers to named constants
- Use decorators for cross-cutting concerns (error handling)
- Write tests for all new functions

### Architecture Principles

- **Modularity**: Each function has a single, clear purpose
- **Testability**: Injectable dependencies, avoid global state
- **Error Handling**: Use decorators for consistent error reporting
- **Type Safety**: Comprehensive type hints for IDE support and validation
- **DRY**: Extract helper functions to eliminate duplication

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📚 [Litmus Documentation](https://docs.litmuschaos.io/)
- 🐛 [Report Issues](https://github.com/Barravar/chaos-actions/issues)
- 💬 [Discussions](https://github.com/Barravar/chaos-actions/discussions)

## Acknowledgments

- Built with [Litmus Chaos](https://litmuschaos.io/)
- Inspired by the chaos engineering community
- Thanks to all contributors

---

**Maintainer**: Barravar Inc. <barravar@barravar.com.br>  
**Repository**: [github.com/Barravar/chaos-actions](https://github.com/Barravar/chaos-actions)
