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

2. Run the initial setup:

```bash
gitplex setup personal
```

The interactive setup will guide you through:
- Configuring your Git identity (email, username)
- Setting up workspace directories
- Adding Git providers (GitHub, GitLab, Azure DevOps)
- Generating and configuring SSH keys

3. Switch between profiles:

```bash
gitplex switch work  # Switch to work profile
gitplex switch personal  # Switch back to personal
```

## ✨ Features

### Core Features
- 🔐 **Smart SSH Management**: 
  - Automated ED25519/RSA key generation
  - Secure key permissions and storage
  - SSH agent integration
  - Provider-specific configurations

- 🎯 **Profile Isolation**: 
  - Separate Git configs per workspace
  - Provider-specific usernames
  - Directory-based profile switching
  - Automatic config updates

- 🌐 **Multi-Provider Support**: 
  - GitHub
  - GitLab
  - Azure DevOps
  - Bitbucket
  - Custom enterprise setups

- 📂 **Workspace Organization**: 
  - Directory-based configurations
  - Automatic workspace setup
  - Profile-specific paths

### Safety Features
- 🛡️ **Automatic Backups**:
  - Backup of existing configurations
  - Timestamped backup archives
  - Easy restoration
  - Backup metadata tracking

- ⚡ **System Checks**:
  - Git installation verification
  - SSH agent status check
  - Configuration conflict detection
  - Permission validation

### User Experience
- 🎨 **Beautiful CLI**:
  - Rich color output
  - Interactive prompts
  - Progress indicators
  - Clear error messages

- 🔄 **Smart Defaults**:
  - Interactive setup
  - Configuration suggestions
  - Safe operation modes
  - Helpful warnings

## 📖 Project History

GitPlex evolved from my personal scripts that I kept copying between machines whenever I needed to set up new Git environments. After years of manually managing multiple `.gitconfig` files and SSH keys, I decided to create a proper tool that would make this process seamless for everyone.

## ⚙️ Configuration

### Basic Profile Setup

```bash
# Interactive setup
gitplex setup work

# Non-interactive setup
gitplex setup work \
  --email work@company.com \
  --username work-user \
  --directory ~/Projects/work \
  --provider github \
  --provider gitlab
```

### Directory Structure

GitPlex creates and manages the following structure:

```
~
├── .gitplex/
│   ├── profiles.json
│   └── backups/
│       └── backup_20240112_120000/
├── .ssh/
│   ├── config
│   ├── personal_github
│   ├── personal_github.pub
│   ├── work_gitlab
│   └── work_gitlab.pub
├── .gitconfig
└── Projects/
    ├── personal/
    │   └── .gitconfig
    └── work/
        └── .gitconfig
```

### CLI Commands

```bash
# List all profiles
gitplex list

# Switch profile
gitplex switch work

# Create backup
gitplex backup ./my-backup-dir

# Restore backup
gitplex restore ./my-backup-dir/backup_20240112_120000
```

## ❓ FAQ

### Is it safe to use?

Yes! GitPlex takes several precautions:
- Creates automatic backups before modifications
- Uses secure permissions for SSH keys
- Validates configurations before applying
- Provides clear warnings and confirmations

### How does GitPlex handle SSH keys?

GitPlex generates ED25519 SSH keys (or RSA as fallback) with:
- Proper file permissions (600/644)
- Secure key generation
- Automatic SSH config updates
- SSH agent integration

### Can I use GitPlex in a team?

Yes! GitPlex is perfect for teams where developers need to:
- Manage multiple Git providers
- Switch between different projects
- Maintain separate configurations
- Share consistent setups

## 🛠️ Development Status

- ✅ **Code Quality**: 
  - Ruff for linting and formatting
  - MyPy for static type checking
  - Comprehensive test coverage
  - Clean code architecture

- ✅ **Platform Support**: 
  - macOS
  - Linux
  - Windows

- ✅ **Provider Support**:
  - GitHub
  - GitLab
  - Azure DevOps
  - Bitbucket

- ✅ **Documentation**: 
  - Clear README
  - Type hints
  - Docstrings
  - Usage examples

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