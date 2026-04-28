#!/usr/bin/env python3
"""Полная песочница с Docker-изоляцией."""

import subprocess, uuid
from typing import Tuple

def execute_in_sandbox(code: str, timeout: int = 10) -> Tuple[int, str, str]:
    container_name = f"sandbox_{uuid.uuid4().hex[:8]}"
    cmd = [
        "docker", "run", "--rm", "--name", container_name,
        "--network", "none",
        "--read-only",
        "--memory", "64m",
        "--cpus", "0.5",
        "python:3.12-slim",
        "python", "-c", code
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        # Вывод ошибок, если они есть
        if proc.returncode != 0:
            print(f"Sandbox error (ret={proc.returncode}): stderr={proc.stderr.strip()}")
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        print("Sandbox timeout")
        return -1, "", "Timeout"
    except Exception as e:
        print(f"Sandbox exception: {e}")
        return -2, "", str(e)

if __name__ == "__main__":
    # Тест 1: безопасный код
    code = "print(1+1)"
    ret, out, err = execute_in_sandbox(code)
    print(f"Safe: ret={ret}, out={out.strip()}, err={err.strip()}")

    # Тест 2: попытка сети
    code = "import urllib.request; urllib.request.urlopen('http://example.com')"
    ret, out, err = execute_in_sandbox(code)
    print(f"Network: ret={ret}, out={out.strip()}, err={err.strip()}")