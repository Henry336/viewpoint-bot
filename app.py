import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# CONFIGURATION: Insert your live BotFather token and Group Chat ID here
TELEGRAM_TOKEN = "8656163968:AAGecUFQj9Evd_T8fcReWEy_8BhVQJdgBC4"
CHAT_ID = "-5478779473"

@app.route('/webhook', methods=['POST'])
def tally_webhook():
    payload = request.json
    if not payload:
        return jsonify({"error": "No payload received"}), 400

    room_number = "Not Specified"
    guest_name = "Not Specified"
    order_items = ""

    # Grab the fields array
    fields = payload.get('data', {}).get('fields', [])

    for field in fields:
        label = field.get('label', '')
        value = field.get('value')
        options = field.get('options', []) # This holds the text for dropdowns

        # 1. TRANSLATE DROPDOWNS: Convert ugly UUIDs back to text
        if isinstance(value, list) and len(value) > 0:
            selected_id = value[0]
            selected_text = ""
            
            # Find the matching ID in the options list
            for opt in options:
                if opt.get('id') == selected_id:
                    selected_text = opt.get('text', '')
                    break
                    
            # Fallback just in case
            if not selected_text:
                 selected_text = str(selected_id)
        else:
            # For standard text inputs
            selected_text = str(value) if value is not None else ""
            
        selected_text = selected_text.strip()

        # 2. FILTER: Skip completely empty answers or "0" selections
        if not selected_text or selected_text == "0":
            continue

        label_lower = label.lower()

        # 3. ROUTE METADATA: Catch Room and Name regardless of exact spelling
        if "room" in label_lower:
            room_number = selected_text
            continue
            
        if "name" in label_lower:
            guest_name = selected_text
            continue

        # 4. FILTER: Ignore structural form fields that shouldn't be on the receipt
        ignore_keywords = ["total", "category", "done ordering"]
        if any(keyword in label_lower for keyword in ignore_keywords):
            continue

        # 5. FORMAT FOOD ITEMS: 
        if selected_text.isdigit():
            # If the answer is a quantity number, print: • 2x Sandwich
            order_items += f"• <b>{selected_text}x</b> {label}\n"
        else:
            # If it's a text answer (like a special request), print normally
            order_items += f"• <i>{label}:</i> {selected_text}\n"

    # Edge Case: Blank order
    if not order_items:
        return jsonify({"status": "ignored", "message": "Empty order"}), 200

    # 6. Construct the Layout
    tg_message = "🛎 <b>NEW ORDER</b>\n"
    tg_message += f"🏢 <b>Room:</b> {room_number}\n"
    tg_message += f"👤 <b>Name:</b> {guest_name}\n\n"
    tg_message += "<b>---------------- ITEMS -------------------</b>\n"
    tg_message += f"{order_items}"
    tg_message += "━━━━━━━━━━━━━━━━━━━━━━━━"

    # 7. POST to Telegram
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)