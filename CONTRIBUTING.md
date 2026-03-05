# Contributing to Litmus Chaos Actions

Thank you for your interest in contributing to Litmus Chaos Actions! We welcome contributions from the community.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git
- Docker (for building container images)

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/chaos-actions.git
   cd chaos-actions
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install runtime dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `requests>=2.31.0` - HTTP library for API calls
   - `urllib3>=2.0.0` - HTTP client
   - `PyYAML>=6.0` - YAML parsing for manifests

4. **Install development dependencies:**
   ```bash
   pip install pytest pytest-cov pytest-mock pre-commit
   ```

   Or install all development dependencies from pyproject.toml:
   ```bash
   pip install -e ".[dev]"
   ```

5. **Set up pre-commit hooks:**
   ```bash
   pre-commit install
   ```

   This will automatically run code quality checks (black, isort, flake8, mypy, bandit) before each commit.

## Running Tests

The project includes comprehensive test coverage (93% overall, 158 tests):

```bash
# Run all tests with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_main_integration.py -v

# Run specific test class
pytest tests/test_monitoring.py::TestWaitExperimentCompletion -v

# Run with debug output
pytest tests/ -v -s
```

Test coverage includes:
- Main workflow integration tests (main.py: 98% coverage)
- Service layer (resources, experiments, monitoring: 95-100% coverage)
- Client API interactions (94% coverage)
- Utility functions (formatters, error handlers: 100% coverage)
- Manifest processing and validation (75% coverage)
- Error handling and edge cases
- Decorator functionality

## Code Quality Tools

The project uses pre-commit hooks for automated code quality checks:

```bash
# Run pre-commit on all files
pre-commit run --all-files

# Run specific hooks
pre-commit run black --all-files
pre-commit run mypy --all-files
```

### Manual Code Quality Checks

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/

# Security scanning
bandit -r src/
```

Configured tools:
- **black**: Code formatting (100 char line length)
- **isort**: Import sorting (black profile)
- **flake8**: Style guide enforcement
- **mypy**: Static type checking (strict mode)
- **bandit**: Security issue scanning

## Local Testing with Real Litmus Instance

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

## Building the Docker Image

```bash
docker build -t chaos-actions:dev .
docker run --env-file .vars chaos-actions:dev
```

## Code Style Guidelines

- **Follow PEP 8** style guidelines
- **Type hints**: Use for all function parameters and returns (Python 3.11+ syntax with `|` for unions)
- **Docstrings**: Add for all public functions and classes (Google style)
- **Function design**: Keep functions focused and modular (single responsibility principle)
- **Naming**: Prefix private/internal functions with `_`
- **Constants**: Extract magic numbers to named constants
- **Cross-cutting concerns**: Use decorators (e.g., error handling)
- **Testing**: Write tests for all new functions

### Example Function

```python
def get_project_id(client: LitmusClient, project_name: str) -> str:
    """
    Retrieve the project ID for a given project name.

    Args:
      client: The LitmusClient instance to use for the call.
      project_name: Name of the project to look up.

    Returns:
      The project ID as a string.

    Raises:
      LitmusRestError: If the request fails.
    """
    # Implementation here
```

## Architecture Principles

- **Modularity**: Each function has a single, clear purpose
- **Testability**: Injectable dependencies, avoid global state
- **Error Handling**: Use decorators for consistent error reporting
- **Type Safety**: Comprehensive type hints for IDE support and validation
- **DRY**: Extract helper functions to eliminate duplication
- **Separation of Concerns**: Use service layer for business logic

## Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make your changes** following the code style guidelines

3. **Add tests** for new functionality

4. **Run pre-commit checks**:
   ```bash
   pre-commit run --all-files
   ```

5. **Run the test suite**:
   ```bash
   pytest tests/ --cov=src
   ```

6. **Commit your changes**:
   ```bash
   git commit -m 'Add amazing feature'
   ```

7. **Push to your fork**:
   ```bash
   git push origin feature/amazing-feature
   ```

8. **Open a Pull Request** on GitHub with:
   - Clear description of changes
   - Link to any related issues
   - Screenshots/examples if applicable

## Review Process

- All PRs require review from at least one maintainer
- CI checks must pass (tests, linting, type checking)
- Code coverage should not decrease
- Follow-up on review comments promptly

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (with sensitive data redacted)

## Questions?

- 📚 [Litmus Documentation](https://docs.litmuschaos.io/)
- 🐛 [Report Issues](https://github.com/Barravar/chaos-actions/issues)
- 💬 [Discussions](https://github.com/Barravar/chaos-actions/discussions)

## Code of Conduct

Be respectful and constructive in all interactions. We're here to collaborate and improve the project together.

---

Thank you for contributing to Litmus Chaos Actions! 🚀
