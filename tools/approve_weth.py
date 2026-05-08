#!/usr/bin/env python3
import os
from web3 import Web3

RPC_URL = os.environ.get("WEB3_RPC_URL", "https://ethereum-sepolia.publicnode.com")
PRIVATE_KEY = os.environ.get("WEB3_PRIVATE_KEY")
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]

def main():
    if not PRIVATE_KEY:
        raise RuntimeError("Set WEB3_PRIVATE_KEY environment variable")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = w3.eth.account.from_key(PRIVATE_KEY)
    w3.eth.default_account = account.address

    token = w3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)

    print(f"Approving WETH for Router {ROUTER_ADDRESS} from {account.address}")
    tx = token.functions.approve(ROUTER_ADDRESS, 2**256 - 1).build_transaction({
        "from": account.address,
        "gas": 100000,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price,  # для Sepolia legacy gas
    })
    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Approve tx sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status == 1:
        print("Approve confirmed! Allowance set to max.")
    else:
        print("Approve failed!")

if __name__ == "__main__":
    main()