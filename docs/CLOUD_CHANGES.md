# Cloud development update — October 5, 2026

The application remains version 0.1.0. The source bundle now defaults to a private GitHub repository and browser-based GitHub Codespaces.

Added `.devcontainer/devcontainer.json`, `.devcontainer/post-create.sh`, and `scripts/cloud-start.sh`. Rewrote README, setup, and costs for the cloud workflow. Retained the earlier local guide in `LOCAL_SETUP.md` as an optional path. Updated architecture, roadmap, validation, and secret/build exclusions.

The development environment requests 2 CPUs and 8 GB of RAM, uses the universal development image plus Docker-in-Docker, and forwards only port 8080 automatically. Port privacy must still be checked in Codespaces. No paid resource or repository was created as part of preparing the ZIP.

The application code and existing Docker deployment remain unchanged. Synthetic data only; Vultr/Microsandbox/MCP remain later milestones.
