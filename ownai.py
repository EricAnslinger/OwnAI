#!/usr/bin/env python3
"""OwnAI — reproducible Runpod runner for Ollama and Open WebUI.

Run as root inside a Runpod PyTorch pod: python3 ownai.py
Requires an exposed HTTP port 8080 in the Runpod pod configuration.
"""

from __future__ import annotations

import os
import pathlib
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


LOGO = r"""
   ___                 ___    ____
  / _ \__    _____    / _ |  /  _/
 / // /| |/|/ / _ \  / __ | _/ /
 \___/ |__,__/_//_/ /_/ |_|/___/

              OwnAI
    Made with Love by Eric Anslinger
"""


@dataclass(frozen=True)
class Config:
    """Central configuration for paths, ports and the Ollama model."""

    home: pathlib.Path
    model: str
    context_length: int = 16384
    ollama_port: int = 11434
    webui_port: int = 8080

    @classmethod
    def from_environment(cls) -> Config:
        return cls(
            home=pathlib.Path(os.getenv("OWNAI_HOME", "/workspace")).expanduser(),
            model=os.getenv("OWNAI_MODEL", "gurubot/GLM-4.5-Air-Derestricted:Q4_K_M"),
        )

    @property
    def models_dir(self) -> pathlib.Path:
        return self.home / "ollama-models"

    @property
    def webui_data_dir(self) -> pathlib.Path:
        return self.home / "open-webui-data"

    @property
    def venv_dir(self) -> pathlib.Path:
        return self.home / "open-webui-venv"

    @property
    def secret_file(self) -> pathlib.Path:
        return self.home / "open-webui-secret"

    @property
    def ollama_url(self) -> str:
        return f"http://127.0.0.1:{self.ollama_port}"

    @property
    def webui_url(self) -> str:
        return f"http://127.0.0.1:{self.webui_port}"

    def ollama_env(self) -> dict[str, str]:
        return {
            **os.environ,
            "OLLAMA_MODELS": str(self.models_dir),
            "OLLAMA_HOST": f"127.0.0.1:{self.ollama_port}",
            "OLLAMA_CONTEXT_LENGTH": str(self.context_length),
        }

    def webui_env(self) -> dict[str, str]:
        if not self.secret_file.exists():
            self.secret_file.write_text(secrets.token_hex(32) + "\n")
            self.secret_file.chmod(0o600)
        return {
            **os.environ,
            "DATA_DIR": str(self.webui_data_dir),
            "OLLAMA_BASE_URL": self.ollama_url,
            "WEBUI_SECRET_KEY": self.secret_file.read_text().strip(),
            "WEBUI_AUTH": "true",
            "ENABLE_SIGNUP": "true",  # Create the first admin account, then disable signup in UI.
        }


class Runner:
    """Execute commands; downloads block until their subprocess completes."""

    @staticmethod
    def info(message: str) -> None:
        print(f"[OwnAI] {message}", flush=True)

    def run(self, *args: object, env: dict[str, str] | None = None,
            capture: bool = False) -> subprocess.CompletedProcess[str]:
        argv = [str(arg) for arg in args]
        self.info("Ausführen: " + " ".join(argv))
        return subprocess.run(argv, env=env, check=True, text=True,
                              capture_output=capture)

    def start_background(self, args: list[object], env: dict[str, str],
                         logfile: pathlib.Path) -> None:
        with logfile.open("ab") as stream:
            subprocess.Popen(
                [str(arg) for arg in args], env=env,
                stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True,
            )


class ServiceManager:
    """Start long-running services and verify that they are actually ready."""

    def __init__(self, config: Config, runner: Runner):
        self.cfg = config
        self.runner = runner

    @staticmethod
    def is_ready(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return 200 <= response.status < 400
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def wait_for(self, url: str, name: str, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_ready(url):
                self.runner.info(f"{name} ist bereit.")
                return
            time.sleep(3)
        raise RuntimeError(f"{name} startet nicht. Prüfe die Logs unter {self.cfg.home}.")

    def start_ollama(self) -> None:
        health_url = self.cfg.ollama_url + "/api/tags"
        if self.is_ready(health_url):
            self.runner.info("Ollama läuft bereits.")
            return
        self.runner.info("Starte Ollama ...")
        self.runner.start_background(
            ["ollama", "serve"], self.cfg.ollama_env(),
            self.cfg.home / "ollama.log",
        )
        self.wait_for(health_url, "Ollama", 120)

    def start_webui(self) -> None:
        if self.is_ready(self.cfg.webui_url):
            self.runner.info("Open WebUI läuft bereits.")
            return
        executable = self.cfg.venv_dir / "bin" / "open-webui"
        if not executable.exists():
            raise RuntimeError(f"Open WebUI nicht installiert: {executable}")
        self.runner.info("Starte Open WebUI ...")
        self.runner.start_background(
            [executable, "serve", "--host", "0.0.0.0", "--port", self.cfg.webui_port],
            self.cfg.webui_env(), self.cfg.home / "open-webui.log",
        )
        self.wait_for(self.cfg.webui_url, "Open WebUI", 300)


class Installer:
    """Idempotent installation of Ollama, the model, and Open WebUI."""

    def __init__(self, config: Config, runner: Runner, services: ServiceManager):
        self.cfg = config
        self.runner = runner
        self.services = services

    def prepare(self) -> None:
        if os.geteuid() != 0:
            raise RuntimeError("Dieses Skript muss im Runpod-Container als root laufen.")
        for directory in (self.cfg.home, self.cfg.models_dir, self.cfg.webui_data_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if shutil.which("nvidia-smi"):
            self.runner.run("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader")
        else:
            self.runner.info("WARNUNG: NVIDIA-GPU wurde nicht erkannt.")
        self.runner.run("apt-get", "update")
        self.runner.run("apt-get", "install", "-y", "curl", "ca-certificates",
                        "python3-venv", "python3-pip", "openssl")

    def install_ollama(self) -> None:
        if not shutil.which("ollama"):
            script = self.cfg.home / "ollama-install.sh"
            self.runner.run("curl", "--fail", "--location", "--show-error",
                            "--silent", "https://ollama.com/install.sh", "--output", script)
            self.runner.run("sh", script)
        else:
            self.runner.info("Ollama ist bereits installiert.")
        self.runner.run("ollama", "--version")

    def install_webui(self) -> None:
        python = self.cfg.venv_dir / "bin" / "python"
        executable = self.cfg.venv_dir / "bin" / "open-webui"
        if executable.exists():
            self.runner.info("Open WebUI ist bereits installiert.")
            return
        if not python.exists():
            self.runner.run(sys.executable, "-m", "venv", self.cfg.venv_dir)
        self.runner.run(python, "-m", "pip", "install", "--upgrade", "pip")
        self.runner.run(python, "-m", "pip", "install", "open-webui")

    def download_model(self) -> None:
        # The server must be running for Ollama CLI operations.
        self.services.start_ollama()
        output = self.runner.run("ollama", "list", env=self.cfg.ollama_env(),
                                 capture=True).stdout
        # Match exact model tags, not incidental substrings.
        installed = {line.split()[0].lower() for line in output.splitlines()[1:] if line.split()}
        if self.cfg.model.lower() in installed:
            self.runner.info("Modell bereits vorhanden – Download wird übersprungen.")
            return
        free_gib = shutil.disk_usage(self.cfg.models_dir).free / 1024**3
        if free_gib < 90:
            raise RuntimeError(
                f"Nicht genug freier Speicher: {free_gib:.1f} GiB; "
                "für den erstmaligen Modelldownload mindestens 90 GiB einplanen."
            )
        self.runner.info(f"Lade {self.cfg.model} herunter. Warte auf vollständigen Download ...")
        self.runner.run("ollama", "pull", self.cfg.model, env=self.cfg.ollama_env())
        self.runner.info("Modelldownload abgeschlossen.")


class OwnAIApp:
    """Coordinates the full installation and starts both local services."""

    def __init__(self, config: Config):
        self.cfg = config
        self.runner = Runner()
        self.services = ServiceManager(config, self.runner)
        self.installer = Installer(config, self.runner, self.services)

    def run(self) -> None:
        print(LOGO, flush=True)
        self.installer.prepare()
        self.installer.install_ollama()
        self.installer.install_webui()
        self.installer.download_model()
        self.services.start_webui()
        self.runner.info("FERTIG! Runpod HTTP-Port 8080 freigeben und Open WebUI öffnen.")
        print(f"Open WebUI (lokal): {self.cfg.webui_url}\n"
              f"Modell: {self.cfg.model}\n"
              f"Logs: {self.cfg.home / 'ollama.log'} und "
              f"{self.cfg.home / 'open-webui.log'}", flush=True)
        self.runner.info("Erstelle dein Admin-Konto und deaktiviere danach weitere Registrierungen.")


def main() -> int:
    try:
        OwnAIApp(Config.from_environment()).run()
        return 0
    except (subprocess.CalledProcessError, RuntimeError, OSError) as error:
        print(f"[OwnAI] FEHLER: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
