import os
import re
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
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Security Middleware ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') == API_KEY:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return decorated

# --- Helper Functions ---
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

def extract_detail(text, pattern, default="Not found"):
    """Helper to run regex and return the first group or a default value."""
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip().replace('\n', ' ') if match and match.group(1) else default

# --- API Endpoints ---

@app.route("/tenders", methods=["GET"])
@require_api_key
def get_tenders():
    # This endpoint remains the same, for fast searching
    try:
        limit = request.args.get('limit', 20, type=int)
        q = request.args.get('q')
        bid_number = request.args.get('bid_number')
        
        fields_to_select = "bid_number, item_category, department, organization, quantity, status, closing_date, tender_amount, city, state, source_url"
        query = supabase.table('tenders').select(fields_to_select)
        
        if q:
            search_columns = 'item_category,department,organization,city,state,status'
            formatted_query = ' | '.join(q.split())
            query = query.text_search(search_columns, formatted_query, config='english')
        
        if bid_number:
            query = query.eq("bid_number", bid_number)

        response = query.limit(limit).execute()
        
        tenders = response.data
        for tender in tenders:
            if tender.get('closing_date'):
                tender['formatted_deadline'] = format_date(tender['closing_date'])
            if tender.get('tender_amount'):
                tender['formatted_amount'] = format_amount(tender['tender_amount'])
        
        return jsonify({"success": True, "count": len(tenders), "data": tenders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- NEW: Detail Extractor Endpoint ---
@app.route("/tender-extract-details", methods=['GET'])
@require_api_key
def get_tender_extracted_details():
    """
    Fetches the full_text of a tender and extracts a rich set of details using regex.
    """
    bid_number = request.args.get('bid_number')
    if not bid_number:
        return jsonify({"success": False, "error": "bid_number parameter is required"}), 400

    try:
        response = supabase.table("tenders").select("full_text").eq("bid_number", bid_number).limit(1).execute()
        if not response.data:
            return jsonify({"success": False, "error": f"Tender not found: {bid_number}"}), 404
        
        full_text = response.data[0].get('full_text', '')
        
        # Define patterns for each piece of information
        patterns = {
            "emd_amount": r'(?:EMD Amount|Earnest Money Deposit|EMD)\D*?([\d,]+)',
            "past_experience_years": r'Years of Past Experience Required[^\n]+\n([\w\s\(\)]+)',
            "mse_exemption": r'MSE Exemption for.*?Turnover\n(Yes|No)',
            "startup_exemption": r'Startup Exemption for.*?Turnover\n(Yes|No)',
            "required_documents": r'Document required from seller[^\n]*\n([^\n]+)',
            "show_docs_to_bidders": r'show documents uploaded by bidders to all bidders[^\n]*\n(Yes|No)',
            "min_bids_for_extension": r'Minimum number of\s*bids required[^\n]*\n(\d+)',
            "past_performance_pct": r'Past Performance[^\n]*\n(\d+\s*%)',
            "ra_enabled": r'Bid to RA enabled[^\n]*\n(Yes|No)',
            "ra_qualification_rule": r'RA Qualification Rule\n([^\n]+)',
            "type_of_bid": r'Type of Bid[^\n]*\n([^\n]+)',
            "tech_clarification_time": r'Time allowed for Technical Clarifications[^\n]*\n([^\n]+)',
            "evaluation_method": r'Evaluation Method[^\n]*\n([^\n]+)',
            "epbg_details": r'ePBG Detail[^\n]*\nAdvisory Bank[^\n]*\n([^\n]+)',
            "beneficiary": r'Beneficiary\s*:\s*\n([^\n]+)',
            "mse_purchase_preference": r'MSE Purchase Preference[^\n]*\n(Yes|No)',
            "mii_purchase_preference": r'MII Purchase Preference[^\n]*\n(Yes|No)'
        }
        
        extracted_data = {"bid_number": bid_number}
        for key, pattern in patterns.items():
            extracted_data[key] = extract_detail(full_text, pattern)
            
        return jsonify({"success": True, "data": extracted_data})

    except Exception as e:
        print(f"Error in /tender-extract-details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Keep your /tender-text endpoint as is
@app.route("/tender-text", methods=['GET'])
@require_api_key
def get_tender_text():
    # This function remains unchanged
    try:
        bid_number = request.args.get('bid_number')
        if not bid_number:
            return jsonify({"success": False, "error": "bid_number parameter is required"}), 400
        response = supabase.table("tenders").select("full_text, department").eq("bid_number", bid_number).limit(1).execute()
        if not response.data:
            return jsonify({"success": False, "error": f"No tender found with bid_number: {bid_number}"}), 404
        return jsonify({"success": True, "data": response.data[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
