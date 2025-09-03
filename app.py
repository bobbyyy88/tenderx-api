import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from functools import wraps
from datetime import datetime
from supabase import create_client, Client

# --- Configuration ---
# Hardcoded environment variables
SUPABASE_URL = "https://plqaquatgjajignchswv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBscWFxdWF0Z2phamlnbmNoc3d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MjMwNzc1NCwiZXhwIjoyMDY3ODgzNzU0fQ.nvPBCAgtwgJ6kGwd3ms9xm17rTlIFe6fEquroE1sjQE"
API_KEY = "tenderx_api_key_123"

# Try to load from .env file if available (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Override with environment variables if they exist
    SUPABASE_URL = os.getenv("SUPABASE_URL", SUPABASE_URL)
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)
    API_KEY = os.getenv("API_KEY", API_KEY)
except ImportError:
    pass  # dotenv not available, continue with hardcoded values

# Flask app ko chalu karna
app = Flask(__name__)
# CORS ko enable karna
CORS(app)

# --- Supabase Connection ---
# Supabase client banana
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase se connection safalta se ban gaya!")
except Exception as e:
    print(f"Supabase se connection me error aaya: {e}")
    # Don't exit, let the app continue to run for debugging

# --- Security Middleware ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == API_KEY:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return decorated

# --- Helper Functions ---
def format_date(date_str):
    """Format date string to readable format"""
    try:
        if not date_str:
            return None
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%d %b %Y")
    except Exception as e:
        print(f"Date formatting error: {e}")
        return date_str

def format_amount(amount):
    """Format amount to Indian currency format"""
    try:
        if not amount:
            return None
        amount = float(amount)
        if amount >= 10000000:  # 1 crore
            return f"₹{amount/10000000:.2f} Cr"
        elif amount >= 100000:  # 1 lakh
            return f"₹{amount/100000:.2f} L"
        else:
            return f"₹{amount:,.2f}"
    except Exception as e:
        print(f"Amount formatting error: {e}")
        return str(amount)

# --- API Endpoints (Routes) ---

@app.route("/")
def home():
    """Ek simple welcome message dikhane ke liye"""
    return "TenderAI ka Flask server chal raha hai!"

@app.route("/health", methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "supabase_url": SUPABASE_URL
    })

@app.route("/tenders", methods=["GET"])
def get_tenders():
    """
    Yeh function 'tenders' table se data nikaal kar laayega.
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 10, type=int)
        status = request.args.get('status')
        location = request.args.get('location')
        
        # Start building query
        query = supabase.table('tenders').select('*').limit(limit)
        
        # Apply filters if provided
        if status:
            query = query.eq("status", status)
        if location:
            query = query.ilike("location", f"%{location}%")
        
        # Execute query
        response = query.execute()
        
        # Process data
        tenders = response.data
        for tender in tenders:
            if 'deadline' in tender:
                tender['formatted_deadline'] = format_date(tender['deadline'])
            if 'amount' in tender:
                tender['formatted_amount'] = format_amount(tender['amount'])
        
        # Agar data milta hai, toh use JSON format me bhejna
        if tenders:
            return jsonify({
                "success": True,
                "count": len(tenders),
                "data": tenders
            })
        else:
            return jsonify({
                "success": False,
                "message": "Koi tender nahi mila."
            }), 404

    except Exception as e:
        # Agar koi error aata hai, toh use dikhana
        print(f"Error in get_tenders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/test-connection", methods=['GET'])
@require_api_key
def test_connection():
    """Test Supabase connection"""
    try:
        # Simple query to test connection
        response = supabase.table("tenders").select("count", count="exact").limit(1).execute()
        count = response.count if hasattr(response, 'count') else 0
        
        return jsonify({
            "success": True,
            "message": "Database connected successfully! 🎉",
            "count": count
        })
    except Exception as e:
        print(f"Connection test error: {e}")
        return jsonify({
            "success": False,
            "message": f"Connection failed: {str(e)}"
        }), 500

@app.route("/public-test", methods=['GET'])
def public_test():
    """Public test endpoint without authentication"""
    return jsonify({
        "success": True,
        "message": "Public endpoint working!",
        "timestamp": datetime.now().isoformat(),
        "supabase_url": SUPABASE_URL
    })

# --- Server ko Chalu Karna ---
if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting server on port {port}")
    # Server ko 0.0.0.0 par chalana taaki woh local network me bhi accessible ho
    app.run(host='0.0.0.0', port=port)
