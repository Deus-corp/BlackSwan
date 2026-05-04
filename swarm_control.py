#!/usr/bin/env python3
"""
BlackSwan Swarm Control Panel – easy CLI menu to manage the swarm.
Run without arguments:
    python3 swarm_control.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"

def run(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Execute a shell command and return the result."""
    return subprocess.run(
        cmd, shell=True, cwd=PROJECT_ROOT, capture_output=True, text=True, check=check
    )

def print_banner():
    print("""
╔══════════════════════════════════════════╗
║        🦢 BlackSwan Swarm Control       ║
╚══════════════════════════════════════════╝
    """)

def show_status():
    """Display container status and last metrics."""
    print("\n📊 Container status:")
    res = run("docker ps --filter 'name=lab_swarm_demo-node' --format 'table {{.Names}}\t{{.Status}}'")
    if res.stdout.strip():
        print(res.stdout)
    else:
        print("   No running nodes.")

    print("\n📈 Last metric (node-1):")
    logs = run("docker logs lab_swarm_demo-node-1 --tail 5 2>&1")
    for line in logs.stdout.splitlines():
        if 'SwarmNode' in line:
            print(f"   {line.strip()}")
            break
    else:
        print("   No data.")

def save_logs():
    """Save logs of all nodes into docs/logs/ with a timestamp."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_dir = PROJECT_ROOT / "docs" / "logs" / f"swarm_logs_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n💾 Saving logs to {dest_dir} ...")
    for i in range(1, 5):
        log = run(f"docker logs lab_swarm_demo-node-{i} 2>&1")
        (dest_dir / f"node-{i}.log").write_text(log.stdout)
    # Also save combined logs
    combined = run(f"docker compose -f {COMPOSE_FILE} logs --no-color 2>&1")
    (dest_dir / "all_nodes.log").write_text(combined.stdout)
    print("✅ Logs saved.")

def set_binance_keys():
    """Guide the user to enter Binance Testnet API keys into .env."""
    env_file = PROJECT_ROOT / ".env"
    print("\n🔑 Set Binance Testnet API keys.")
    print("(Leave blank to keep existing value.)")
    api_key = input("API Key: ").strip()
    api_secret = input("API Secret: ").strip()

    if not api_key and not api_secret:
        print("No changes made.")
        return

    # Read existing .env content or create empty
    if env_file.exists():
        lines = env_file.read_text().splitlines()
    else:
        lines = []

    new_lines = []
    found_key = False
    found_secret = False
    for line in lines:
        if line.startswith("BINANCE_TESTNET_API_KEY="):
            if api_key:
                new_lines.append(f"BINANCE_TESTNET_API_KEY={api_key}")
                found_key = True
            else:
                new_lines.append(line)
                found_key = True
        elif line.startswith("BINANCE_TESTNET_API_SECRET="):
            if api_secret:
                new_lines.append(f"BINANCE_TESTNET_API_SECRET={api_secret}")
                found_secret = True
            else:
                new_lines.append(line)
                found_secret = True
        else:
            new_lines.append(line)

    if not found_key and api_key:
        new_lines.append(f"BINANCE_TESTNET_API_KEY={api_key}")
    if not found_secret and api_secret:
        new_lines.append(f"BINANCE_TESTNET_API_SECRET={api_secret}")

    env_file.write_text("\n".join(new_lines) + "\n")
    print("✅ API keys updated in .env file.")

def menu():
    while True:
        print_banner()
        print("1. 🚀 Start swarm (default 4 nodes)")
        print("2. ⏹️  Stop swarm")
        print("3. 🔄 Rebuild & start (build --no-cache)")
        print("4. 📊 Status")
        print("5. 📜 View logs (real-time, Ctrl+C to exit)")
        print("6. ⚙️  Change LLM model")
        print("7. 🌐 Change market mode (sim / live / web3)")
        print("8. 🔑 Set Binance API keys")
        print("9. 💾 Save logs to file")
        print("10. 📁 Open docker-compose.async.yml in nano")
        print("0. 🚪 Exit")
        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            nodes = input("Number of nodes (default 4): ").strip() or "4"
            run(f"docker compose -f {COMPOSE_FILE} up -d --scale node={nodes}")
            print("✅ Swarm started.")
            time.sleep(2)
        elif choice == "2":
            run(f"docker compose -f {COMPOSE_FILE} down")
            print("✅ Swarm stopped.")
        elif choice == "3":
            run(f"docker compose -f {COMPOSE_FILE} down")
            print("🔨 Rebuilding...")
            run(f"docker compose -f {COMPOSE_FILE} build --no-cache", check=True)
            nodes = input("Number of nodes (default 4): ").strip() or "4"
            run(f"docker compose -f {COMPOSE_FILE} up -d --scale node={nodes}")
            print("✅ Rebuilt and started.")
        elif choice == "4":
            show_status()
        elif choice == "5":
            print("📜 Logs (press Ctrl+C to exit)...")
            try:
                subprocess.run(
                    f"docker compose -f {COMPOSE_FILE} logs -f --tail 30",
                    shell=True, cwd=PROJECT_ROOT
                )
            except KeyboardInterrupt:
                pass
        elif choice == "6":
            print("\nAvailable models: deepseek, qwen, smollm2, llama1b, smollm17, smollm360, abl_qwen05, abl_llama1b, unc_llama1b")
            model = input("Enter model key: ").strip()
            if model:
                content = COMPOSE_FILE.read_text()
                # Replace existing LLM_MODEL line
                new_content = content.replace(f'LLM_MODEL=', '#LLM_MODEL=')
                new_content = new_content.replace('#LLM_MODEL=', f'LLM_MODEL={model}', 1)
                COMPOSE_FILE.write_text(new_content)
                print(f"✅ Model changed to {model}. Restart the swarm (option 3) to apply.")
        elif choice == "7":
            print("\nModes: sim, live, web3")
            mode = input("Enter market mode: ").strip()
            if mode in ('sim', 'live', 'web3'):
                content = COMPOSE_FILE.read_text()
                new_content = content.replace('MARKET_MODE=', '#MARKET_MODE=')
                new_content = new_content.replace('#MARKET_MODE=', f'MARKET_MODE={mode}', 1)
                COMPOSE_FILE.write_text(new_content)
                print(f"✅ Market mode changed to {mode}. Restart the swarm (option 3) to apply.")
        elif choice == "8":
            set_binance_keys()
        elif choice == "9":
            save_logs()
        elif choice == "10":
            try:
                subprocess.run(f"nano {COMPOSE_FILE}", shell=True, cwd=PROJECT_ROOT)
            except Exception:
                print("❌ Could not open nano. Please edit the file manually.")
        elif choice == "0":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid choice.")

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    menu()