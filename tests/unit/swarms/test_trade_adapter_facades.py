def test_trade_adapter_facades_import() -> None:
    import src.swarms.trade.adapters.base as base
    import src.swarms.trade.adapters.futures as futures
    import src.swarms.trade.adapters.live_market as live_market
    import src.swarms.trade.adapters.multi_pair as multi_pair
    import src.swarms.trade.adapters.nonce as nonce
    import src.swarms.trade.adapters.orderbook as orderbook
    import src.swarms.trade.adapters.tradingview as tradingview
    import src.swarms.trade.adapters.web3_testnet as web3_testnet

    assert base is not None
    assert futures is not None
    assert live_market is not None
    assert multi_pair is not None
    assert nonce is not None
    assert orderbook is not None
    assert tradingview is not None
    assert web3_testnet is not None