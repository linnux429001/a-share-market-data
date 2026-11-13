# Trade risk audit (experimental)
This is an offline calculator, not a buy/sell recommendation or order execution system.
Run: `python -m unittest -v test_trade_risk_audit.py`.
Inputs: entry, quantity, hypothetical stop, equity and per-trade risk budget.
Outputs: notional, estimated loss at stop, risk budget and a share cap.
Limitations: no verified exchange timestamps, transaction costs, slippage, gap risk,
liquidity modeling, market regime classifier or backtested predictive edge.
Do not use its outputs as evidence that a stop can execute at the stop price.
The live collector and main branch remain unchanged.
