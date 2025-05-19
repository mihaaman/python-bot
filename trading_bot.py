from flask import Flask, request, jsonify
from pybit.unified_trading import HTTP
import os

app = Flask(__name__)

# Настройка API Bybit (вставь свои ключи)
BYBIT_API_KEY = "QrSPgmkUjcKBYUBDRm"  # Замени на свой API-ключ Bybit
BYBIT_API_SECRET = "vCudYRjhXWVMQCDmvhiW8PjF1CAajn1vM535"  # Замени на свой API-секрет Bybit
client = HTTP(
    testnet=False,  # Укажи True, если используешь тестовую сеть
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

# Обработчик для корневого пути (для UptimeRobot)
@app.route('/')
def health_check():
    return "Server is running", 200

# Обработчик вебхуков от TradingView
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        print(f"Received webhook: {data}")

        signal = data.get("signal")
        symbol = data.get("symbol")
        price = data.get("price")
        size_pct = float(data.get("size_pct", 0))

        # Проверка депозита (баланс на Bybit)
        balance = client.get_wallet_balance(accountType="UNIFIED")["result"]["list"][0]["totalEquity"]
        balance = float(balance)
        print(f"Current balance: {balance}")

        # Рассчитываем размер позиции
        position_size = (balance * size_pct / 100) / price  # Количество контрактов (примерный расчёт)
        leverage = 30  # Плечо 30x, как ты хотел

        # Устанавливаем плечо
        try:
            client.set_leverage(symbol=symbol, buyLeverage=str(leverage), sellLeverage=str(leverage))
            print(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            print(f"Error setting leverage: {e}")

        # Логика обработки сигналов
        if signal == "Buy":
            # Открываем лонг
            try:
                order = client.place_order(
                    symbol=symbol,
                    side="Buy",
                    order_type="Market",
                    qty=str(position_size),
                    time_in_force="GTC"
                )
                print(f"Opened Long: {symbol}, Price: {price}, Size: {size_pct}% ({position_size} contracts)")
                return jsonify({"status": "success", "message": "Long opened"}), 200
            except Exception as e:
                print(f"Error opening Long: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        elif signal == "Sell":
            # Открываем шорт
            try:
                order = client.place_order(
                    symbol=symbol,
                    side="Sell",
                    order_type="Market",
                    qty=str(position_size),
                    time_in_force="GTC"
                )
                print(f"Opened Short: {symbol}, Price: {price}, Size: {size_pct}% ({position_size} contracts)")
                return jsonify({"status": "success", "message": "Short opened"}), 200
            except Exception as e:
                print(f"Error opening Short: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        elif signal == "CloseAll":
            # Закрываем все позиции
            try:
                positions = client.get_positions(symbol=symbol, category="linear")["result"]["list"]
                for position in positions:
                    if position["size"] != "0":
                        side = "Sell" if position["side"] == "Buy" else "Buy"
                        client.place_order(
                            symbol=symbol,
                            side=side,
                            order_type="Market",
                            qty=position["size"],
                            time_in_force="GTC"
                        )
                print(f"Closed all positions: {symbol}, Price: {price}")
                return jsonify({"status": "success", "message": "All positions closed"}), 200
            except Exception as e:
                print(f"Error closing positions: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        else:
            print(f"Unknown signal: {signal}")
            return jsonify({"status": "error", "message": "Unknown signal"}), 400

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
