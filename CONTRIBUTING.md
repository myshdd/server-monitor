# Contributing to Server Monitor

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version)
- Relevant logs

### Suggesting Features

Feature requests are welcome! Please:
- Check existing issues first
- Describe the feature and use case
- Explain why it would be useful

### Pull Requests

1. **Fork** the repository
2. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/your-feature-name

    Make your changes:
        Follow existing code style
        Add comments for complex logic
        Update documentation if needed
    Test your changes:

    Bash

    python3 -m py_compile bots/*.py
    /usr/local/bin/validate-config.sh

    Commit with clear messages:

    Bash

    git commit -m "feat: add new monitoring feature"

    Use conventional commits:
    feat:, fix:, docs:, refactor:
    Push and create a Pull Request

Code Style

    Python: Follow PEP 8
    Bash: Use shellcheck for validation
    Comments: Write clear, concise comments
    Configuration: Use JSON for configs, keep secrets separate

Project Structure

text

/opt/server-monitor/
├── bots/          # Telegram bots (Python)
├── scripts/       # Helper scripts (Bash)
├── config/        # Configuration files
├── lib/           # Shared libraries
└── install/       # Installation scripts

Security

    Never commit secrets (tokens, passwords, IPs)
    Use config/secrets.json for sensitive data
    Report security issues privately via GitHub Security Advisories

Questions?

Feel free to open an issue for questions or discussion.

Thank you for contributing! 🚀
