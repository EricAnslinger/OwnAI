# OwnAI

OwnAI is a Python setup script for quickly deploying a self-hosted AI environment on Runpod. It installs Ollama and Open WebUI and downloads a configurable language model.

The project is intended for temporary GPU pods: create an instance, run the script, use the model for a short period, and delete the pod when you're done.

## Features

- Installs Ollama and Open WebUI
- Downloads `gurubot/GLM-4.5-Air-Derestricted:Q4_K_M` by default
- Lets you change the model in `ownai.py`
- Checks for an NVIDIA GPU
- Starts the required services and checks their availability
- Keeps model files, application data, and logs under `/workspace` by default
- Can be rerun on a fresh Runpod instance

## Requirements

- Runpod GPU pod with a compatible NVIDIA GPU and 120 GB memory
- Ubuntu-based environment (the Runpod PyTorch template is recommended)
- Python 3
- Enough VRAM and disk space for your chosen model
- **HTTP port `8080` exposed in Runpod before starting the setup**

The default model is large; a GPU with 96 GB VRAM is a practical choice. Smaller Ollama models can run on GPUs with less memory.

## Installation

Before deploying your pod, add **`8080`** to **Expose HTTP Ports** in the Runpod pod configuration. Open WebUI uses this port. Without it, the Runpod HTTP proxy will not be able to reach the interface.

Open your Runpod terminal and run:

```bash
apt-get update && apt-get install -y git
cd /workspace
git clone https://github.com/EricAnslinger/OwnAI.git
cd OwnAI
python3 ownai.py
```

The script runs installation and download commands sequentially and waits for each command to finish. Existing components are reused where possible.

## Changing the model

You can select a different model directly in `ownai.py`. Find the model setting and replace its Ollama identifier:

```python
model: str = "gurubot/GLM-4.5-Air-Derestricted:Q4_K_M"
```

For example:

```python
model: str = "qwen3:32b"
```

Use a model available through Ollama, and choose a GPU with enough VRAM for its size and context length.

## Usage

Once installation finishes, open Open WebUI through your pod's Runpod HTTP proxy link:

```text
https://YOUR-POD-ID-8080.proxy.runpod.net
```

Ollama listens locally on port `11434`.

Check which models are installed:

```bash
ollama list
```

Check which model is currently loaded and whether it is running on the GPU:

```bash
ollama ps
```

If your pod restarts and the files are still present, rerun the setup script:

```bash
cd /workspace/OwnAI
python3 ownai.py
```

## Configuration and storage

OwnAI defaults to `/workspace`. You can choose another base directory with `OWNAI_HOME`:

```bash
export OWNAI_HOME=/workspace/ownai
python3 ownai.py
```

Model downloads, Open WebUI data, and logs are stored under the configured directory.

## Temporary deployments

OwnAI is designed for situations where you need your own AI model for a limited time, not for maintaining a permanent server.

The workflow is to start a GPU pod, install OwnAI, use the model, and terminate the pod afterward. This avoids paying for an idle GPU. A future pod can be provisioned and configured again using the same script.

**Deleting a pod can delete local model files, chat history, and application settings.** Back up anything you need or attach a separate Runpod Network Volume if you want data to survive pod deletion. Network Volumes may continue to incur charges after the GPU pod is removed.

## Security

Create an Open WebUI administrator account and disable public sign-ups afterward. Runpod proxy links can be publicly accessible, so protect the interface with a strong password or use a private access method. Do not expose Ollama's port `11434` publicly or commit secrets, API keys, or private keys to the repository.

## Author

Eric Anslinger
