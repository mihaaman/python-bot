from flask import Flask, request, jsonify
import ccxt
import logging
import json

# Настройка логирования
logging.basicConfig(filename='trading_bot.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

app = Flask(__name__)

# Настройки Bybit
bybit = ccxt.bybit({
    'apiKey': 'QrSPgmkUjcKBYUBDRm',
    'secret': 'vCudYRjhXWVMQCDmvhiW8PjF1CAajn1vM535',
    'enableRateLimit': True,
})

# Глобальные переменные
main_deposit = 100.0
cycle_deposit = main_deposit
buy_trade_count = 0
sell_trade_count = 0
in_cycle = False
trade_percentages = [10.0, 15.0, 20.0, 25.0, 30.0]
leverage = 30.0
symbol = 'XRPUSDT'
margin_mode = 'isolated'
max_consecutive_trades = 5
min_position_usd = 1.0

# Установка левериджа и маржинального режима
def set_leverage_and_margin(symbol):
    try:
        bybit.set_leverage(leverage, symbol=symbol)
        bybit.set_margin_mode(margin_mode, symbol=symbol)
        logging.info(f"Set leverage {leverage}x and margin mode {margin_mode} for {symbol}")
    except Exception as e:
        logging.error(f"Error setting leverage/margin: {str(e)}")

# Обработка вебхуков
@app.route('/webhook', methods=['POST'])
def webhook():
    global main_deposit, cycle_deposit, buy_trade_count, sell_trade_count, in_cycle
    try:
        data = request.get_json()
        signal = data.get('signal')
        symbol = data.get('symbol')
        price = float(data.get('price'))
        size_pct = float(data.get('size_pct', 10.0))

        logging.info(f"Received webhook: {data}")

        balance = bybit.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        if usdt_balance < min_position_usd:
            logging.error(f"Insufficient balance: {usdt_balance} USDT")
            return jsonify({'status': 'error', 'message': 'Insufficient balance'}), 400

        if signal == 'Buy' and buy_trade_count < max_consecutive_trades and not in_cycle:
            in_cycle = True
            cycle_deposit = usdt_balance
            logging.info(f"Cycle Started (Long), Cycle Deposit: {cycle_deposit}")
            buy_trade_count += 1
            position_usd = cycle_deposit * (size_pct / 100)
            if position_usd < min_position_usd:
                logging.info(f"Buy Signal Skipped: Position USD {position_usd} below minimum")
                return jsonify({'status': 'skipped', 'message': 'Position too small'}), 200
            amount = (position_usd * leverage) / price
            order = bybit.create_market_buy_order(symbol, amount)
            logging.info(f"Opened Long: {amount} {symbol} at {price}, Size: {size_pct}%")
            return jsonify({'status': 'success', 'message': 'Long opened'}), 200

        elif signal == 'Sell' and sell_trade_count < max_consecutive_trades and not in_cycle:
            in_cycle = True
            cycle_deposit = usdt_balance
            logging.info(f"Cycle Started (Short), Cycle Deposit: {cycle_deposit}")
            sell_trade_count += 1
            position_usd = cycle_deposit * (size_pct / 100)
            if position_usd < min_position_usd:
                logging.info(f"Sell Signal Skipped: Position USD {position_usd} below minimum")
                return jsonify({'status': 'skipped', 'message': 'Position too small'}), 200
            amount = (position_usd * leverage) / price
            order = bybit.create_market_sell_order(symbol, amount)
            logging.info(f"Opened Short: {amount} {symbol} at {price}, Size: {size_pct}%")
            return jsonify({'status': 'success', 'message': 'Short opened'}), 200

        elif signal == 'CloseAll':
            in_cycle = False
            buy_trade_count = 0
            sell_trade_count = 0
            main_deposit = usdt_balance
            logging.info(f"Cycle Closed, Main Deposit Updated: {main_deposit}")
            position = bybit.fetch_position(symbol)
            if position['contracts'] > 0:
                if position['side'] == 'long':
                    bybit.create_market_sell_order(symbol, position['contracts'])
                else:
                    bybit.create_market_buy_order(symbol, position['contracts'])
            logging.info(f"Closed All Positions at {price}")
            return jsonify({'status': 'success', 'message': 'All positions closed'}), 200

        else:
            logging.info(f"Invalid or skipped signal: {signal}")
            return jsonify({'status': 'skipped', 'message': 'Invalid signal'}), 200

    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    set_leverage_and_margin(symbol)
    app.run(host='0.0.0.0', port=5000)

