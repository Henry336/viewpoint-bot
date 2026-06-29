import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# CONFIGURATION: Insert your live BotFather token and Group Chat ID here
TELEGRAM_TOKEN = "8656163968:AAGecUFQj9Evd_T8fcReWEy_8BhVQJdgBC4"
CHAT_ID = "-5478779473"

@app.route('/webhook', methods=['POST'])
def tally_webhook():
    # 1. Grab the JSON payload sent by Tally
    payload = request.json
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    room_number = "Not Specified"
    guest_name = "Not Specified"
    order_items = ""

    # 2. Extract fields list safely from Tally payload
    fields = payload.get('data', {}).get('fields', [])

    for field in fields:
        label = field.get('label', '')
        value = field.get('value')

        # Capture Room Number Dropdown
        if label == "Room Number":
            if value:
                room_number = str(value)
            continue

        # Capture Guest Name Input
        if label == "Name":
            if value:
                guest_name = str(value)
            continue

        # DROPDOWN FILTER: Process items where an actual quantity was selected
        if value:
            val_str = str(value).strip().lower()
            # Ignore selections that mean zero or empty
            if val_str not in ["0", "none", "", "false"]:
                order_items += f"• <b>{value}x</b> {label}\n"

    # 3. Edge Case: Blank order (if they somehow submitted without picking food)
    if not order_items:
        return jsonify({"status": "ignored", "message": "Empty order"}), 200

    # 4. Construct your custom structured layout
    tg_message = "🛎 <b>NEW ORDER</b>\n"
    tg_message += f"🏢 <b>Room:</b> {room_number}\n"
    tg_message += f"👤 <b>Name:</b> {guest_name}\n\n"
    tg_message += "<b>---------------- ITEMS -------------------</b>\n"
    tg_message += f"{order_items}"
    tg_message += "━━━━━━━━━━━━━━━━━━━━━━━━"

    # 5. POST data directly to Telegram Bot API endpoint
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload_tg = {
        "chat_id": CHAT_ID,
        "text": tg_message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload_tg)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Telegram API Error: {e}")
        return jsonify({"error": "Failed to send to Telegram"}), 500

    return jsonify({"status": "success", "message": "Order routed to kitchen"}), 200

if __name__ == '__main__':
    # Fallback to port 5000 for local execution if running natively
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)