import requests

data = {
    'strategy_id': 'sma_crossover.py',
    'symbol': 'NVDA',
    'cash': 100000,
    'start_date': '2024-01-01',
    'end_date': '2024-12-31',
    'commission': 0.001
}

resp = requests.post('http://127.0.0.1:8000/api/backtest', json=data)
result = resp.json()

if 'metrics' in result:
    m = result['metrics']
    end_value = m.get('end_value')
    pnl = m.get('pnl')
    buy_count = m.get('buy_count')
    sell_count = m.get('sell_count')
    print(f"结束价值: {end_value}")
    print(f"收益: {pnl}")
    print(f"买: {buy_count}, 卖: {sell_count}")
else:
    print(f"错误: {result}")