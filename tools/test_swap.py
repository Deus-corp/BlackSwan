#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from adapters.web3_testnet import Web3TestnetAdapter

adapter = Web3TestnetAdapter()
print(f"Account: {adapter.account.address}")
print(f"WETH balance: {adapter._get_token_balance('0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14')}")
print(f"ETH balance: {adapter.w3.from_wei(adapter.w3.eth.get_balance(adapter.account.address), 'ether')} ETH")

result = adapter.place_order("sell", 0.001)
print("Swap result:", result)