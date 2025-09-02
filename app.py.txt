import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from supabase import create_client, Client
import logging
from datetime import datetime

# --- 1. CONFIGURATION ---
app = Flask(__name__)
CORS(app)  # Enable CORS for Botpress integration

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase Client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# API Key for security
API_KEY = os.environ.get("API_KEY")  # Set this in Render environment variables

# --- 2. SECURITY MIDDLEWARE ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == API_KEY:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return decorated

# --- 3. HELPER FUNCTIONS ---
def format_date(date_str):
    """Format date string to readable format"""
    try:
        if not date_str:
            return None
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%d %b %Y")
    except Exception as e:
        logger.error(f"Date formatting error: {e}")
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
        logger.error(f"Amount formatting error: {e}")
        return str(amount)

# --- 4. API ENDPOINTS ---

# Health check endpoint
@app.route("/health", methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# Test Supabase connection
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
        logger.error(f"Connection test error: {e}")
        return jsonify({
            "success": False,
            "message": f"Connection failed: {str(e)}"
        }), 500

# Get all tenders
@app.route("/tenders", methods=['GET'])
@require_api_key
def get_tenders():
    """Get all tenders with optional filtering"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 20, type=int)
        status = request.args.get('status')
        location = request.args.get('location')
        category = request.args.get('category')
        search = request.args.get('search')
        
        # Start building query
        query = supabase.table("tenders").select("*").order("created_at", desc=True).limit(limit)
        
        # Apply filters if provided
        if status:
            query = query.eq("status", status)
        if location:
            query = query.ilike("location", f"%{location}%")
        if category:
            query = query.eq("category", category)
        if search:
            # Simple search implementation - can be improved
            query = query.or_(f"title.ilike.%{search}%,description.ilike.%{search}%")
        
        # Execute query
        response = query.execute()
        
        # Process data
        tenders = response.data
        for tender in tenders:
            if 'deadline' in tender:
                tender['formatted_deadline'] = format_date(tender['deadline'])
            if 'amount' in tender:
                tender['formatted_amount'] = format_amount(tender['amount'])
        
        return jsonify({
            "success": True,
            "count": len(tenders),
            "data": tenders
        })
    except Exception as e:
        logger.error(f"Get tenders error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Get tender by ID or bid number
@app.route("/tender", methods=['GET'])
@require_api_key
def get_tender():
    """Get tender by ID or bid number"""
    try:
        tender_id = request.args.get('id')
        bid_number = request.args.get('bid_number')
        
        if not tender_id and not bid_number:
            return jsonify({
                "success": False,
                "error": "Either id or bid_number parameter is required"
            }), 400
        
        # Query by ID or bid number
        if tender_id:
            response = supabase.table("tenders").select("*").eq("id", tender_id).execute()
        else:
            response = supabase.table("tenders").select("*").eq("bid_number", bid_number).execute()
        
        if not response.data:
            return jsonify({
                "success": False,
                "error": f"No tender found with the given parameters"
            }), 404
        
        # Process data
        tender = response.data[0]
        if 'deadline' in tender:
            tender['formatted_deadline'] = format_date(tender['deadline'])
        if 'amount' in tender:
            tender['formatted_amount'] = format_amount(tender['amount'])
        
        return jsonify({
            "success": True,
            "data": tender
        })
    except Exception as e:
        logger.error(f"Get tender error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Log user query
@app.route("/log-query", methods=['POST'])
@require_api_key
def log_user_query():
    """Log user query to Supabase"""
    try:
        data = request.json
        required_fields = ['user_id', 'query']
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        # Add timestamp if not provided
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Insert into user_queries table
        response = supabase.table("user_queries").insert(data).execute()
        
        return jsonify({
            "success": True,
            "message": "Query logged successfully"
        })
    except Exception as e:
        logger.error(f"Log query error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Get tender statistics
@app.route("/stats", methods=['GET'])
@require_api_key
def get_stats():
    """Get tender statistics"""
    try:
        # Get total count
        total_response = supabase.table("tenders").select("count", count="exact").execute()
        total_count = total_response.count if hasattr(total_response, 'count') else 0
        
        # Get status counts
        status_counts = {}
        statuses = ["active", "archived", "pending", "draft"]
        
        for status in statuses:
            status_response = supabase.table("tenders").select("count", count="exact").eq("status", status).execute()
            status_counts[status] = status_response.count if hasattr(status_response, 'count') else 0
        
        # Get recent tenders
        recent_response = supabase.table("tenders").select("id,title,status,created_at").order("created_at", desc=True).limit(5).execute()
        recent_tenders = recent_response.data
        
        return jsonify({
            "success": True,
            "total_count": total_count,
            "status_counts": status_counts,
            "recent_tenders": recent_tenders
        })
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# --- 5. ERROR HANDLING ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({"success": False, "error": str(e)}), 500

# --- 6. RUN THE APP ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    logger.info(f"Starting Flask API on port {port}")
    logger.info(f"Supabase URL: {supabase_url}")
    
    app.run(host="0.0.0.0", port=port)
