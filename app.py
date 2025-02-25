from flask import Flask, request, jsonify
import json
import time

KEY_FILE = "keys.json"
app = Flask(__name__)

# Load keys from file into a global dictionary
def load_keys():
    try:
        with open(KEY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"daily_keys": {}, "monthly_keys": {}}

# Save keys to file (for persistence)
def save_keys(keys_data):
    with open(KEY_FILE, "w") as f:
        json.dump(keys_data, f, indent=4)

# Global keys store (in a real production system, you might use a database and proper locking)
keys_data = load_keys()

@app.route("/api/authenticate", methods=["POST"])
def authenticate():
    data = request.get_json()
    user_key = data.get("key", "").strip()
    current_time = time.time()

    # Check both daily and monthly keys
    for key_type in ["daily_keys", "monthly_keys"]:
        if user_key in keys_data.get(key_type, {}):
            key_info = keys_data[key_type][user_key]
            expiry = key_info.get("expiry", 0)
            in_use = key_info.get("in_use", False)

            if current_time > expiry:
                return jsonify({"success": False, "message": "Key expired. Please purchase a new key."}), 403

            if in_use:
                return jsonify({"success": False, "message": "Key is busy. Already in use on another computer."}), 403

            # Mark the key as in use
            keys_data[key_type][user_key]["in_use"] = True
            save_keys(keys_data)
            return jsonify({"success": True, "message": "Key accepted. Access granted."})

    return jsonify({"success": False, "message": "Invalid key."}), 403

@app.route("/api/release", methods=["POST"])
def release():
    data = request.get_json()
    user_key = data.get("key", "").strip()

    for key_type in ["daily_keys", "monthly_keys"]:
        if user_key in keys_data.get(key_type, {}):
            keys_data[key_type][user_key]["in_use"] = False
            save_keys(keys_data)
            return jsonify({"success": True, "message": "Key released."})

    return jsonify({"success": False, "message": "Invalid key."}), 403

if __name__ == "__main__":
    # For production, you might run this via a WSGI server (e.g., Gunicorn or Waitress)
    app.run(host="0.0.0.0", port=5000)
