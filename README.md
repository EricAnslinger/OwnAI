# OwnAI

OwnAI is a Python-based setup script for deploying a self-hosted AI environment on Runpod. It automates the installation and configuration of Ollama, Open WebUI, and a locally hosted language model.

The project is intended for users who want to run their own AI models on cloud GPUs without manually setting up the entire environment each time.

## Features

- Automated installation of Ollama and Open WebUI
- Downloads and configures GLM-4.5-Air-Derestricted (Q4_K_M)
- NVIDIA GPU detection
- Automatic startup of required services
- Persistent storage for models and application data
- Reusable setup for new Runpod instances
- Basic service health checks and logging

## Requirements

- Runpod GPU instance with a compatible NVIDIA GPU
- Ubuntu-based environment (Runpod PyTorch template recommended)
- Python 3
- At least 96 GB GPU memory recommended for the configured model
- Sufficient disk space for model weights and application data

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/OwnAI.git
cd OwnAI
```

Run the setup script:

```bash
python3 ownai.py
```

The script installs the required components, downloads the configured model, and starts the services. Existing installations are reused where possible.

## Usage

Once the installation is complete, Open WebUI can be accessed through port `8080`.

For Runpod, expose port `8080` under the pod's HTTP port settings and open the corresponding proxy URL.

Ollama runs locally on port `11434`.

To check installed models:

```bash
ollama list
```

To check GPU utilization:

```bash
ollama ps
```

To start the environment again after a pod restart:

```bash
python3 ownai.py
```

## Configuration

OwnAI uses `/workspace` as its default installation directory.

A different directory can be configured using the `OWNAI_HOME` environment variable:

```bash
export OWNAI_HOME=/workspace/ownai
python3 ownai.py
```

Application data, model files, and logs are stored under the configured directory.

For persistent storage across pod deletion, use a separate Runpod Network Volume or back up the required files externally.

## Security

Open WebUI should be protected with user authentication. Public registration should be disabled after the administrator account has been created.

Do not expose the Ollama API directly to the internet or commit credentials, API keys, or application secrets to the repository.

## Author

Eric Anslinger
