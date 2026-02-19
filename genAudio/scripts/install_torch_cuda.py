"""
Instala PyTorch y torchaudio con soporte CUDA en el entorno actual.
Ejecutar con el Python del venv: .venv\\Scripts\\python.exe scripts\\install_torch_cuda.py

Opcional: scripts/install_torch_cuda.py cu121  -> usa CUDA 12.1 en lugar de 12.4
"""
from __future__ import annotations

import subprocess
import sys

# cu124 = CUDA 12.4 (recomendado RTX 30/40). cu121 = CUDA 12.1 para drivers más antiguos.
CUDA_VERSION = sys.argv[1] if len(sys.argv) > 1 else "cu124"
INDEX_URL = f"https://download.pytorch.org/whl/{CUDA_VERSION}"


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def main() -> None:
    print("Desinstalando torch y torchaudio (versión actual)...")
    run([sys.executable, "-m", "pip", "uninstall", "-y", "torch", "torchaudio"])
    print(f"Instalando torch y torchaudio con CUDA ({CUDA_VERSION})...")
    run([
        sys.executable, "-m", "pip", "install",
        "torch", "torchaudio",
        "--index-url", INDEX_URL,
    ])
    print("Comprobando CUDA...")
    import torch
    if torch.cuda.is_available():
        print(f"  CUDA disponible: {torch.cuda.get_device_name(0)}")
    else:
        print("  CUDA no disponible. Comprueba drivers NVIDIA y que el índice sea correcto para tu sistema.")


if __name__ == "__main__":
    main()
