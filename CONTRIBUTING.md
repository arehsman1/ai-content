# Contributing to AI Content Discovery Assistant

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in the required values
5. Run the smoke test:
   ```bash
   PYTHONPATH=. python scripts/smoke_test.py
   ```

## Development Workflow

- Create a feature branch from `main`
- Make your changes
- Ensure the smoke test still passes
- Follow PEP 8 and the existing code style
- Add or update docstrings for public functions and classes
- Open a pull request with a clear description of the change

## Code Style

- Python 3.12+
- Type hints where appropriate
- Docstrings for public classes and functions
- Keep modules focused and small
- No hardcoded secrets

## Reporting Issues

- Use GitHub Issues for bugs and feature requests
- Include steps to reproduce, expected vs actual behavior, and environment details
- For security issues, see [SECURITY.md](SECURITY.md)

## Pull Request Process

1. Update documentation if needed
2. Add an entry to `CHANGELOG.md` under an `[Unreleased]` section if the change is user-facing
3. Ensure CI (when available) and the smoke test pass
4. Request review from a maintainer

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
