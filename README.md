# GitPlex 🔄

> Your Smart Git Profile Manager - One Tool, Multiple Identities

[![PyPI version](https://badge.fury.io/py/gitplex.svg)](https://badge.fury.io/py/gitplex)
[![Python Version](https://img.shields.io/pypi/pyversions/gitplex)](https://pypi.org/project/gitplex)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

GitPlex is an elegant command-line tool designed to solve the common challenge of managing multiple Git identities. Whether you're juggling between work, personal, and open-source projects, GitPlex makes it effortless to maintain separate Git profiles with their own SSH keys, configurations, and workspace settings.

## ✨ Key Features

- 🔐 **Advanced SSH Management**: 
  - Automated ED25519/RSA key generation
  - Secure key permissions (600/644)
  - SSH agent integration
  - Provider-specific configurations
  - Clear key fingerprint display
  - Easy-to-copy public key format

- 🎯 **Profile Isolation**: 
  - Separate Git configs per workspace
  - Provider-specific usernames
  - Directory-based profile switching
  - Automatic config updates
  - Multiple email support
  - GPG key integration

- 🌐 **Multi-Provider Support**: 
  - GitHub
  - GitLab
  - Azure DevOps
  - Bitbucket
  - Custom enterprise setups
  - Provider-specific SSH configs

- 📂 **Workspace Organization**: 
  - Directory-based configurations
  - Automatic workspace setup
  - Profile-specific paths
  - Workspace isolation
  - Smart directory management

- 🛡️ **Comprehensive Backups**:
  - Automatic backup before changes
  - Timestamped backup archives
  - Easy restoration process
  - Backup metadata tracking
  - Separate Git/SSH backups

- ⚡ **System Validation**:
  - Git installation verification
  - SSH agent status check
  - Configuration conflict detection
  - Permission validation
  - Key integrity checks

- 🎨 **Beautiful CLI**:
  - Rich color output
  - Interactive prompts
  - Progress indicators
  - Clear error messages
  - Helpful warnings

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
- Generating and configuring SSH keys with proper permissions
- Creating automatic backups of existing configurations
- Setting up GPG signing (optional)

3. Switch between profiles:

```bash
gitplex switch work  # Switch to work profile
gitplex switch personal  # Switch back to personal
```

## 📖 Advanced Usage

### Profile Management

```bash
# List all profiles with details
gitplex list

# Create a new profile non-interactively
gitplex setup work \
  --email work@company.com \
  --username work-user \
  --directory ~/Projects/work \
  --provider github

# Update profile settings
gitplex update work --email new@work.com

# Delete a profile
gitplex delete work [--keep-files] [--keep-credentials]
```

### SSH Key Management

```bash
# View SSH key details
gitplex keys list

# Test SSH connection
gitplex keys test github

# Copy public key
gitplex keys copy github

# Rotate SSH keys
gitplex keys rotate github
```

### Backup and Restore

```bash
# Create manual backup
gitplex backup create ./my-backup-dir

# List available backups
gitplex backup list

# Restore from backup
gitplex backup restore ./backup_20240112_120000 [--type git|ssh]
```

### Provider Management

```bash
# Add new provider to profile
gitplex provider add work gitlab

# Remove provider
gitplex provider remove work gitlab

# List configured providers
gitplex provider list work
```

## ⚙️ Configuration Structure

GitPlex creates and manages the following structure:

```
~
├── .gitplex/
│   ├── profiles.json
│   └── backups/
│       └── backup_20240112_120000/
│           ├── gitconfig_backup.tar
│           └── ssh_backup.tar
├── .ssh/
│   ├── config
│   ├── id_personal_ed25519
│   ├── id_personal_ed25519.pub
│   ├── id_work_ed25519
│   └── id_work_ed25519.pub
├── .gitconfig
└── Projects/
    ├── personal/
    │   └── .gitconfig
    └── work/
        └── .gitconfig
```

## 🛡️ Security Features

- **SSH Key Security**:
  - ED25519 keys by default (RSA fallback available)
  - Proper file permissions (600 for private, 644 for public)
  - Automatic SSH agent management
  - Key isolation per provider
  - Secure key generation parameters

- **Configuration Safety**:
  - Automatic backups before changes
  - Configuration validation
  - Safe defaults
  - Error prevention
  - Conflict detection

- **Workspace Protection**:
  - Isolated environments
  - Profile-specific settings
  - Directory permission checks
  - Safe file operations
  - Conflict prevention

## 🤝 Contributing

Contributions are welcome! If you'd like to help improve GitPlex:

1. Fork the repository
2. Create a feature branch
3. Write your changes
4. Write tests that prove your changes work
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">Made with ❤️ by the GitPlex community</p>