import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# CONFIGURATION: Insert your live BotFather token and Group Chat ID here
TELEGRAM_TOKEN = "8656163968:AAGecUFQj9Evd_T8fcReWEy_8BhVQJdgBC4"
CHAT_ID = "-5475737451" # change this based on which group chat you're using to test the bot
CURRENCY = "MMK" # Change this to USD or whatever the hotel uses

# THE MENU BRAIN: Updated with your exact new Tally item names and their prices
MENU_PRICES = {
    # Breakfast
    "Nan Gyi Salad": 5000,
    "Tofu Noodles": 4500,
    
    # Lunch
    "Shan Noodles": 5000,
    "Fried Vermicelli Noodles": 6000,
    
    # Dinner
    "Pashu Fried Rice": 7500,
    "Fish Rice Salad": 9000
}

# HARD-CODED CATEGORY MAP: Enforces strict data isolation
MENU_MAP = {
    "Breakfast": ["Nan Gyi Salad", "Tofu Noodles"],
    "Lunch": ["Shan Noodles", "Fried Vermicelli Noodles"],
    "Dinner": ["Pashu Fried Rice", "Fish Rice Salad"]
}

@app.route('/webhook', methods=['POST'])
def tally_webhook():
    payload = request.json
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    fields = payload.get('data', {}).get('fields', [])

    # =========================================================================
    # PASS 1: DETERMINISTIC CATEGORY EXTRACTION
    # =========================================================================
    user_final_category = "Unknown"
    for field in fields:
        label_lower = field.get('label', '').lower()
        if "menu category" in label_lower or "category" in label_lower:
            val = field.get('value')
            options = field.get('options', [])
            
            if isinstance(val, list) and len(val) > 0:
                selected_id = val[0]
                user_final_category = next((opt.get('text', '') for opt in options if opt.get('id') == selected_id), "Unknown")
            elif isinstance(val, str) and val.strip():
                user_final_category = val.strip()
            break

    # If the category couldn't be parsed, fallback to look for valid selections
    if user_final_category not in MENU_MAP:
        print(f"Warning: Extracted category '{user_final_category}' not recognized in MENU_MAP.")

    # Default values for metadata
    room_number = "Not Specified"
    guest_name = "Not Specified"
    order_date = "Not Specified"
    order_time = "Not Specified"
    special_requests = "None"
    
    order_items = ""
    total_sum = 0

    # =========================================================================
    # PASS 2: RUTHLESS DATA FILTERING AND PARSING
    # =========================================================================
    for field in fields:
        label = field.get('label', '')
        value = field.get('value')
        options = field.get('options', [])
        label_lower = label.lower()

        # Handle dropdown conversion
        if isinstance(value, list) and len(value) > 0:
            selected_id = value[0]
            selected_text = next((opt.get('text', '') for opt in options if opt.get('id') == selected_id), str(selected_id))
        else:
            selected_text = str(value) if value is not None else ""
            
        selected_text = selected_text.strip()

        # Filter out empty answers
        if not selected_text or selected_text == "0":
            continue

        # Extract Metadata (Room, Name, Date, Time, Requests)
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

        # Filter out structural Tally calculation fields and headers
        ignore_keywords = ["total", "category", "done ordering", "menu"]
        if any(keyword == label_lower or label_lower.endswith(" menu") for keyword in ignore_keywords):
            continue

        # STRICT FRONTEND BLIND-SPOT FILTER: Discard ghost items from inactive categories
        is_food_item = label in MENU_PRICES or any(label in items for items in MENU_MAP.values())
        if is_food_item:
            allowed_items_for_cat = MENU_MAP.get(user_final_category, [])
            if label not in allowed_items_for_cat:
                print(f"Server Rule Intercepted: Discarded item '{label}' since it does not belong to '{user_final_category}'.")
                continue

        # Process Valid Food Items & Calculate Prices
        if selected_text.isdigit():
            qty = int(selected_text)
            price_per_item = MENU_PRICES.get(label, 0) 
            line_total = qty * price_per_item
            total_sum += line_total
            
            if price_per_item > 0:
                order_items += f"- <b>{qty}x</b> {label} ({line_total:,} {CURRENCY})\n"
            else:
                order_items += f"- <b>{qty}x</b> {label}\n"
        else:
            order_items += f"- <i>{label}:</i> {selected_text}\n"

    if not order_items:
        return jsonify({"status": "ignored", "message": "Empty order after category filtering"}), 200

    # =========================================================================
    # MULTI-LINE STRING FORMATTING FOR TELEGRAM DELIVERY
    # =========================================================================
    tg_message = f"🛎 <b>NEW ORDER ({user_final_category.upper()})</b>\n"
    tg_message += f"<b>Room</b>: {room_number}\n"
    tg_message += f"<b>Name</b>: {guest_name}\n"
    tg_message += f"<b>Date</b>: {order_date}\n"
    tg_message += f"<b>Time</b>: {order_time}\n\n"
    
    tg_message += "<b>-- ITEMS --</b>\n"
    tg_message += f"{order_items}\n"
    tg_message += f"<b>Total: {total_sum:,} {CURRENCY}</b>\n"
    tg_message += "_________________________________\n\n"
    tg_message += f"<b>Special Request:</b>\n{special_requests}"

    # Send payload to Telegram
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