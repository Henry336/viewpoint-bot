import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# CONFIGURATION: Insert your live BotFather token and Group Chat ID here
TELEGRAM_TOKEN = "8656163968:AAGecUFQj9Evd_T8fcReWEy_8BhVQJdgBC4"
CHAT_ID = "-5475737451" # change this based on which group chat you're using to test the bot
CURRENCY = "MMK" # Change this to USD or whatever the hotel uses

# THE MENU BRAIN: Add your exact Tally item names and their single-item prices here
MENU_PRICES = {
    "Nan Gyi Thoke": 5000,
    "Mont Hin Ga": 4500,
    "Fried Rice": 6000,
    "Shan Noodles": 5000,
    "Noodle Salad": 4000,
    "Fried Vermicelli Noodles": 6000,
    "Kong Bong Chicken + Rice": 8000,
    "Rice + Salad": 3500,
    "Rice + Sweet & Sour Pork": 8500,
    "Rice + Grilled Fish": 9000
}

@app.route('/webhook', methods=['POST'])
def tally_webhook():
    payload = request.json
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    # Default values
    room_number = "Not Specified"
    guest_name = "Not Specified"
    order_date = "Not Specified"
    order_time = "Not Specified"
    special_requests = "None"
    
    order_items = ""
    total_sum = 0

    fields = payload.get('data', {}).get('fields', [])

    for field in fields:
        label = field.get('label', '')
        value = field.get('value')
        options = field.get('options', [])
        label_lower = label.lower()

        # 1. Translate Dropdowns (UUIDs -> Text)
        if isinstance(value, list) and len(value) > 0:
            selected_id = value[0]
            selected_text = next((opt.get('text', '') for opt in options if opt.get('id') == selected_id), str(selected_id))
        else:
            selected_text = str(value) if value is not None else ""
            
        selected_text = selected_text.strip()

        # Filter out empty answers
        if not selected_text or selected_text == "0":
            continue

        # 2. Extract Metadata (Room, Name, Date, Time, Requests)
        if "room" in label_lower:
            room_number = selected_text
            continue
        if "name" in label_lower:
            guest_name = selected_text
            continue
        now = datetime.now()
        order_date = now.strftime("%Y-%m-%d")
        order_time = now.strftime("%H:%M:%S")
        if "special request" in label_lower or "notes" in label_lower:
            special_requests = selected_text
            continue

        # Filter out structural Tally fields
        ignore_keywords = ["total", "category", "done ordering"]
        if any(keyword in label_lower for keyword in ignore_keywords):
            continue

        # 3. Process Food Items & Calculate Prices
        if selected_text.isdigit():
            qty = int(selected_text)
            
            # Look up the price. If it's not in the dictionary, it defaults to 0.
            price_per_item = MENU_PRICES.get(label, 0) 
            line_total = qty * price_per_item
            total_sum += line_total
            
            # Format: - 2x Mont Hin Ga (9000 MMK)
            # The {line_total:,} adds commas for thousands (e.g., 9,000)
            if price_per_item > 0:
                order_items += f"- <b>{qty}x</b> {label} ({line_total:,} {CURRENCY})\n"
            else:
                # Fallback if price isn't set in the dictionary
                order_items += f"- <b>{qty}x</b> {label}\n"
        else:
            # Catch-all for non-numeric answers that slipped through
            order_items += f"- <i>{label}:</i> {selected_text}\n"

    if not order_items:
        return jsonify({"status": "ignored", "message": "Empty order"}), 200

    # 4. Construct the Final Layout exactly as requested
    tg_message = "🛎 <b>NEW ORDER</b>\n"
    tg_message += f"<b>Room</b>: {room_number}\n"
    tg_message += f"<b>Name</b>: {guest_name}\n"
    tg_message += f"<b>Date</b>: {order_date}\n"
    tg_message += f"<b>Time</b>: {order_time}\n\n"
    
    tg_message += "<b>-- ITEMS --</b>\n"
    tg_message += f"{order_items}\n"
    tg_message += f"<b>Total: {total_sum:,} {CURRENCY}</b>\n"
    tg_message += "_________________________________\n\n"
    tg_message += f"<b>Special Request:</b>\n{special_requests}"

    # 5. Send to Telegram
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

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)