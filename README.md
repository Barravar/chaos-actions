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
├── README.md                  # This file
└── .github/
    └── src/
        ├── Dockerfile         # Container image definition
        ├── requirements.txt   # Python dependencies
        ├── action.py          # Main script
        ├── classes.py         # Client and configuration classes
        ├── models.py          # Data models
        ├── chaos_types.py     # Type definitions
        └── serializers.py     # JSON serialization utilities
```

## Architecture

The action is built using Python 3 and runs in a Docker container. Key components:

- **LitmusClient**: HTTP client with retry logic for REST and GraphQL APIs
- **LitmusConfig**: Configuration validation and normalization
- **Type-safe Models**: Structured data models for API requests
- **Error Handling**: Custom exceptions for different failure scenarios

## Development

### Local Testing

1. Clone the repository:
   ```bash
   git clone https://github.com/Barravar/chaos-actions.git
   cd chaos-actions/.github/src
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
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

4. Run the script:
   ```bash
   python3 action.py
   ```

### Building the Docker Image

```bash
cd chaos-actions
docker build -t chaos-actions:dev .github/src/
```

### Running Tests

```bash
# Run with a test manifest
export EXPERIMENT_MANIFEST="./experiment_manifest.yaml"
python3 action.py
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
- Use type hints for all function parameters and returns
- Add docstrings for all public functions and classes
- Keep functions focused and modular

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
