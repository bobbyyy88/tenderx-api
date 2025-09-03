import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# --- Configuration ---
# Yeh .env file se aapke secret keys load karega
load_dotenv()

# Flask app ko chalu karna
app = Flask(__name__)
# CORS ko enable karna taaki aapka Lovable.ai frontend isse baat kar sake
CORS(app)

# --- Supabase Connection ---
# .env file se URL aur Key lena
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Check karna ki keys maujood hain ya nahi
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Kripya SUPABASE_URL aur SUPABASE_SERVICE_ROLE_KEY ko .env file me set karein")

# Supabase client banana
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase se connection safalta se ban gaya!")
except Exception as e:
    print(f"Supabase se connection me error aaya: {e}")
    exit()

# --- API Endpoints (Routes) ---

@app.route("/")
def home():
    """Ek simple welcome message dikhane ke liye"""
    return "TenderAI ka Flask server chal raha hai!"

@app.route("/tenders", methods=["GET"])
def get_tenders():
    """
    Yeh function 'tenders' table se data nikaal kar laayega.
    """
    try:
        # 'tenders' table se saare columns (*) select karna, sirf 10 results laana
        response = supabase.table('tenders').select('*').limit(10).execute()
        
        # Agar data milta hai, toh use JSON format me bhejna
        if response.data:
            return jsonify(response.data)
        else:
            return jsonify({"message": "Koi tender nahi mila."}), 404

    except Exception as e:
        # Agar koi error aata hai, toh use dikhana
        return jsonify({"error": str(e)}), 500

# --- Server ko Chalu Karna ---
if __name__ == "__main__":
    # Server ko 0.0.0.0 par chalana taaki woh local network me bhi accessible ho
    app.run(host='0.0.0.0', port=5000)
