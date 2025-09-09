import os
import re # Import the regular expression module
from flask import Flask, jsonify, request
from flask_cors import CORS
from functools import wraps
from datetime import datetime
from supabase import create_client, Client

# --- Configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://plqaquatgjajignchswv.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBscWFxdWF0Z2phamlnbmNoc3d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MjMwNzc1NCwiZXhwIjoyMDY3ODgzNzU0fQ.nvPBCAgtwgJ6kGwd3ms9xm17rTlIFe6fEquroE1sjQE")
API_KEY = os.getenv("API_KEY", "tenderx_api_key_123")

app = Flask(__name__)
CORS(app)

# --- Supabase Connection ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase connection successful!")
except Exception as e:
    print(f"Supabase connection error: {e}")

# --- Security Middleware ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') == API_KEY:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return decorated

# --- Helper Functions (keep as is) ---
def format_date(date_str):
    try:
        if not date_str: return None
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%d %b %Y")
    except: return date_str

def format_amount(amount):
    try:
        if not amount: return None
        amount = float(amount)
        if amount >= 10000000: return f"₹{amount/10000000:.2f} Cr"
        elif amount >= 100000: return f"₹{amount/100000:.2f} L"
        else: return f"₹{amount:,.2f}"
    except: return str(amount)

# --- API Endpoints ---

@app.route("/tenders", methods=["GET"])
@require_api_key
def get_tenders():
    """
    Handles fetching tenders. Now supports generic keyword search via the 'q' parameter.
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        q = request.args.get('q') # For generic keyword search
        bid_number = request.args.get('bid_number')

        # Define the columns for the list view to keep it fast
        fields_to_select = (
            "bid_number, item_category, department, organization, quantity, status, "
            "closing_date, tender_amount, city, state, source_url"
        )
        
        query = supabase.table('tenders').select(fields_to_select).limit(limit)
        
        # --- NEW: Full-Text Search Logic ---
        if q:
            # Search across multiple relevant text columns
            search_columns = 'item_category,department,organization,city,state'
            # Supabase text_search uses '|' for OR logic between words
            formatted_query = ' | '.join(q.split())
            query = query.text_search(search_columns, formatted_query)
        
        if bid_number:
            query = query.eq("bid_number", bid_number)

        response = query.execute()
        
        tenders = response.data
        for tender in tenders:
            if 'closing_date' in tender and tender['closing_date']:
                tender['formatted_deadline'] = format_date(tender['closing_date'])
            if 'tender_amount' in tender and tender['tender_amount']:
                tender['formatted_amount'] = format_amount(tender['tender_amount'])
        
        return jsonify({"success": True, "count": len(tenders), "data": tenders})

    except Exception as e:
        print(f"Error in get_tenders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --- NEW ENDPOINT: Extract EMD Amount ---
@app.route("/tender-emd", methods=['GET'])
@require_api_key
def get_tender_emd():
    """
    Fetches the full_text of a tender and extracts the EMD amount.
    """
    try:
        bid_number = request.args.get('bid_number')
        if not bid_number:
            return jsonify({"success": False, "error": "bid_number parameter is required"}), 400

        # Fetch only the full_text to be efficient
        response = supabase.table("tenders").select("full_text").eq("bid_number", bid_number).limit(1).execute()
        
        if not response.data:
            return jsonify({"success": False, "error": f"No tender found with bid_number: {bid_number}"}), 404
        
        full_text = response.data[0].get('full_text', '')
        
        # Regex to find EMD Amount. Looks for keywords followed by numbers.
        # This can be improved over time with more examples.
        emd_match = re.search(r'(?:EMD Amount|Earnest Money Deposit|EMD)\D*([\d,]+)', full_text, re.IGNORECASE)
        
        emd_amount = None
        if emd_match:
            # The amount is in the first capturing group
            emd_amount = emd_match.group(1)

        if emd_amount:
            return jsonify({
                "success": True,
                "data": {
                    "bid_number": bid_number,
                    "emd_amount": emd_amount
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "EMD amount not found in the tender document."
            }), 404

    except Exception as e:
        print(f"Error in get_tender_emd: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Keep your other endpoints like /tender-text, /health, etc. as they are.

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
