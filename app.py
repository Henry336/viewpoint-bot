import os
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# CONFIGURATION
TELEGRAM_TOKEN = "8656163968:AAGecUFQj9Evd_T8fcReWEy_8BhVQJdgBC4"
CHAT_ID = "-5475737451" 
CURRENCY = "MMK"

# THE MENU BRAIN (Strict Whitelist)
MENU_PRICES = {
    "Nan Gyi Salad": 5000,
    "Tofu Noodles": 4500,
    "Shan Noodles": 5000,
    "Fried Vermicelli Noodles": 6000,
    "Pashu Fried Rice": 7500,
    "Fish Rice Salad": 9000
}

# THE CATEGORY MAP (For ghost-item filtering)
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
    # STEP 1: CLEANLY PARSE ALL DATA
    # Convert Tally's complex JSON into a simple, readable list of dictionaries
    # =========================================================================
    parsed_fields = []
    for field in fields:
        label = field.get('label', '').strip()
        val = field.get('value')
        options = field.get('options', [])
        
        # Extract text safely from dropdown UUIDs or raw text
        if isinstance(val, list) and len(val) > 0:
            selected_id = val[0]
            text = next((opt.get('text', '') for opt in options if opt.get('id') == selected_id), str(selected_id))
        else:
            text = str(val) if val is not None else ""
            
        text = text.strip()
        # Only keep fields that actually have a user-entered value (> 0)
        if text and text != "0": 
            parsed_fields.append({"label": label, "text": text})

    # =========================================================================
    # STEP 2: EXTRACT METADATA & CATEGORY
    # =========================================================================
    user_final_category = "Unknown"
    room_number = "Not Specified"
    guest_name = "Not Specified"
    special_requests = "None"
    
    for item in parsed_fields:
        lbl_lower = item['label'].lower()
        if "category" in lbl_lower:
            user_final_category = item['text']
        elif "room" in lbl_lower:
            room_number = item['text']
        elif "name" in lbl_lower:
            guest_name = item['text']
        elif "special request" in lbl_lower or "notes" in lbl_lower:
            special_requests = item['text']

    # =========================================================================
    # STEP 3: SET TIMEZONE TO MYANMAR (UTC +6:30)
    # =========================================================================
    mm_tz = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(mm_tz)
    order_date = now.strftime("%Y-%m-%d")
    order_time = now.strftime("%I:%M:%S %p") # 12-hour format with AM/PM

    # =========================================================================
    # STEP 4: STRICT WHITELIST ITEM PROCESSING
    # =========================================================================
    order_items = ""
    total_sum = 0
    allowed_items = MENU_MAP.get(user_final_category, [])

    for item in parsed_fields:
        label = item['label']
        text = item['text']
        
        # STRICT RULE 1: Is this explicitly a food item in our price list?
        if label in MENU_PRICES:
            
            # STRICT RULE 2: Does it belong to the category the user submitted under?
            if label not in allowed_items:
                continue # If no, discard it silently.
                
            # If it passes both rules, calculate it!
            if text.isdigit():
                qty = int(text)
                price = MENU_PRICES[label]
                line_total = qty * price
                total_sum += line_total
                order_items += f"- <b>{qty}x</b> {label} ({line_total:,} {CURRENCY})\n"

    # Stop execution if order is empty after all filtering
    if not order_items:
        return jsonify({"status": "ignored", "message": "Empty order after strict filtering"}), 200

    # =========================================================================
    # STEP 5: SEND TO TELEGRAM
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