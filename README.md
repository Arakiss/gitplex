# GitPlex 🔄

> Seamlessly manage multiple Git identities and workspaces

[![PyPI version](https://badge.fury.io/py/gitplex.svg)](https://badge.fury.io/py/gitplex)
[![Python Version](https://img.shields.io/pypi/pyversions/gitplex)](https://pypi.org/project/gitplex)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

GitPlex is a powerful Python tool I created to solve the common challenge of managing multiple Git identities across different providers and workspaces. Like a control center for your Git personas, it seamlessly handles SSH keys, configurations, and workspace isolation.

## 🎯 Why GitPlex?

As a developer, I found myself constantly struggling with:
- Switching between work and personal Git accounts
- Managing different SSH keys for various Git providers
- Accidentally committing with the wrong email
- Maintaining separate workspace configurations
- Supporting multiple Git providers (GitHub, GitLab, Azure DevOps)

I built GitPlex to solve these challenges by:
- Automating SSH key management
- Creating isolated workspace environments
- Ensuring correct Git configurations
- Supporting multiple Git providers seamlessly

## 🚀 Quick Start

1. Install GitPlex via pip:

```bash
pip install gitplex
```

2. Set up your first profile:

```python
from gitplex import ProfileManager

# Initialize the manager
manager = ProfileManager()

# Setup your personal profile
manager.setup_profile(
    name="personal",
    email="personal@email.com",
    username="personal-username",
    directories=["~/Projects/personal"],
    providers=["github", "gitlab"]
)
```

## ✨ Features

- 🔐 **Smart SSH Management**: Automated generation and configuration of SSH keys
- 🎯 **Profile Isolation**: Separate configurations for different Git identities
- 🌐 **Multi-Provider Support**: Works with GitHub, GitLab, Azure DevOps, and more
- 📂 **Workspace Organization**: Structured directory management for different profiles
- 🔄 **Easy Switching**: Seamless switching between different Git identities
- 🛡️ **Security First**: Proper file permissions and SSH key protection
- 🎨 **Cross-Platform**: Works on macOS, Linux, and Windows

## 📖 Project History

GitPlex evolved from my personal scripts that I kept copying between machines whenever I needed to set up new Git environments. After years of manually managing multiple `.gitconfig` files and SSH keys, I decided to create a proper tool that would make this process seamless for everyone.

Key features that make GitPlex unique:
- Automated SSH key generation and management
- Directory-based profile switching
- Support for multiple Git providers
- Cross-platform compatibility
- Security-focused design

## ⚙️ Configuration

### Basic Profile Setup

```python
manager.setup_profile(
    name="work",
    email="work@company.com",
    username="work-username",
    directories=["~/Projects/work"],
    providers=[
        {
            "name": "azure-devops",
            "organization": "company",
            "username": "work-azure"
        },
        {
            "name": "github",
            "username": "work-github"
        }
    ]
)
```

### Directory Structure

GitPlex creates and manages the following structure:

```
~
├── .ssh/
│   ├── config
│   ├── personal_key
│   ├── personal_key.pub
│   ├── work_key
│   └── work_key.pub
├── .gitconfig
└── Projects/
    ├── personal/
    │   └── .gitconfig
    └── work/
        └── .gitconfig
```

### CLI Usage

GitPlex can also be used from the command line:

```bash
# Setup new profile
gitplex setup personal --email personal@email.com --username personal-user

# List profiles
gitplex list

# Switch profile
gitplex switch work

# Backup profiles
gitplex backup ./backup-dir
```

## ❓ FAQ

### Why the name "GitPlex"?

The name combines "Git" with "multiplex", reflecting the tool's ability to manage multiple Git identities and configurations simultaneously. Like a multiplexer that can handle multiple signals, GitPlex handles multiple Git profiles seamlessly.

### How does GitPlex handle SSH keys?

GitPlex generates ED25519 SSH keys (or RSA as fallback) with proper permissions and passphrases. It automatically configures the SSH agent and manages the keys securely.

### Can I use GitPlex in a team?

Yes! GitPlex is perfect for teams where developers need to manage multiple Git providers or maintain separate work/personal configurations.

## 🛠️ Development Status

- ✅ **Code Quality**: 
  - Ruff for linting and formatting
  - MyPy for static type checking
  - Comprehensive test coverage
- ✅ **Platform Support**: 
  - macOS
  - Linux
  - Windows
- ✅ **Provider Support**:
  - GitHub
  - GitLab
  - Azure DevOps
  - Bitbucket
- ✅ **Documentation**: Clear README and type hints

## 🤝 Contributing

While I maintain this project personally, contributions are welcome! If you'd like to help improve GitPlex:
- Check the issues page for current tasks
- Follow the code style guidelines
- Add tests for new features
- Update documentation as needed

See the [Contributing Guidelines](CONTRIBUTING.md) for detailed instructions.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">Crafted with 🔄 by <a href="https://github.com/arakiss">Arakiss</a></p>