#!/usr/bin/env python3
import os
from web3 import Web3

RPC_URL = os.environ.get("WEB3_RPC_URL", "https://ethereum-sepolia.publicnode.com")
WETH = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
QUOTER = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"

QUOTER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "path", "type": "bytes"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
        ],
        "name": "quoteExactInput",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
# Главное исправление: оборачиваем адрес Quoter в checksum
quoter = w3.eth.contract(address=w3.to_checksum_address(QUOTER), abi=QUOTER_ABI)

amount_in = w3.to_wei(1, "ether")  # 1 WETH
fees = [100, 500, 3000, 10000]

print("Проверяю пулы WETH/USDC на Sepolia...")
for fee in fees:
    path = (
        w3.to_bytes(hexstr=WETH).rjust(20, b"\0")
        + fee.to_bytes(3, "big")
        + w3.to_bytes(hexstr=USDC).rjust(20, b"\0")
    )
    try:
        amount_out = quoter.functions.quoteExactInput(path, amount_in).call()
        if amount_out > 0:
            print(f"✅ fee={fee} работает! 1 WETH = {amount_out / 1e6} USDC")
        else:
            print(f"❌ fee={fee} пул, вероятно, не существует или без ликвидности")
    except Exception as e:
        print(f"❌ fee={fee} ошибка: {e}")