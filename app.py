from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string, flash
import json
import time
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # for secure sessions

# Set your admin password (could be stored in an environment variable)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "your_default_admin_password")

KEY_FILE = "keys.json"

# Load keys from file (if missing, initialize with empty dicts)
def load_keys():
    try:
        with open(KEY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"daily_keys": {}, "monthly_keys": {}}

def save_keys(keys_data):
    with open(KEY_FILE, "w") as f:
        json.dump(keys_data, f, indent=4)

# Global key store
keys_data = load_keys()

# ------------------------
# API endpoints for key authentication
# ------------------------

@app.route("/api/authenticate", methods=["POST"])
def authenticate():
    data = request.get_json()
    user_key = data.get("key", "").strip()
    current_time = time.time()
    # Check daily and monthly keys
    for key_type in ["daily_keys", "monthly_keys"]:
        if user_key in keys_data.get(key_type, {}):
            key_info = keys_data[key_type][user_key]
            expiry = key_info.get("expiry", 0)
            if current_time > expiry:
                return jsonify({"success": False, "message": "Key expired. Please obtain a new key."}), 403
            if key_info.get("in_use", False):
                return jsonify({"success": False, "message": "Key already in use on another computer."}), 403
            # Mark the key as in use and update the last used timestamp
            keys_data[key_type][user_key]["in_use"] = True
            keys_data[key_type][user_key]["last_used"] = current_time
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

# ------------------------
# Admin UI for managing keys
# ------------------------

# Simple decorator for routes that require admin login
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# Admin login page
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid password.")
    return render_template_string("""
        <h2>Admin Login</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Enter admin password" required>
            <button type="submit">Login</button>
        </form>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <ul>
            {% for message in messages %}
              <li>{{ message }}</li>
            {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}
    """)

@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("logged_in", None)
    return redirect(url_for("admin_login"))

# Admin dashboard
@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template_string("""
        <h2>Admin Dashboard</h2>
        <ul>
            <li><a href="{{ url_for('admin_add_key') }}">Add New Key</a></li>
            <li><a href="{{ url_for('admin_list_keys') }}">View All Keys</a></li>
            <li><a href="{{ url_for('admin_logout') }}">Logout</a></li>
        </ul>
    """)

# Form to add a new key
@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add_key():
    if request.method == "POST":
        key_value = request.form.get("key_value", "").strip()
        key_type = request.form.get("key_type", "").strip()  # "daily_keys" or "monthly_keys"
        try:
            expiry = float(request.form.get("expiry", 0))
        except ValueError:
            flash("Invalid expiry format. Use a Unix timestamp.")
            return redirect(url_for("admin_add_key"))
        owner = request.form.get("owner", "").strip()  # optional owner field
        if key_type not in ["daily_keys", "monthly_keys"]:
            flash("Invalid key type.")
        elif not key_value:
            flash("Key value cannot be empty.")
        else:
            keys_data.setdefault(key_type, {})[key_value] = {
                "expiry": expiry,
                "in_use": False,
                "last_used": None,
                "owner": owner
            }
            save_keys(keys_data)
            flash("Key added successfully.")
            return redirect(url_for("admin_list_keys"))
    return render_template_string("""
        <h2>Add New Key</h2>
        <form method="post">
            <label>Key Value:</label><br>
            <input type="text" name="key_value" required><br><br>
            <label>Key Type:</label><br>
            <select name="key_type">
                <option value="daily_keys">Daily Key</option>
                <option value="monthly_keys">Monthly Key</option>
            </select><br><br>
            <label>Expiry (Unix Timestamp):</label><br>
            <input type="number" name="expiry" required><br><br>
            <label>Owner (optional):</label><br>
            <input type="text" name="owner"><br><br>
            <button type="submit">Add Key</button>
        </form>
        <br>
        <a href="{{ url_for('admin_dashboard') }}">Back to Dashboard</a>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <ul>
            {% for message in messages %}
              <li>{{ message }}</li>
            {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}
    """)

# List keys and show details (expiry, usage, last used, owner) with an option to delete
@app.route("/admin/list")
@login_required
def admin_list_keys():
    return render_template_string("""
        <h2>All Keys</h2>
        <h3>Daily Keys</h3>
        <ul>
        {% for key, info in keys_data.get('daily_keys', {}).items() %}
            <li>
                <strong>{{ key }}</strong><br>
                Expiry: {{ info.expiry }}<br>
                In Use: {{ info.in_use }}<br>
                Last Used: {{ info.last_used }}<br>
                Owner: {{ info.owner }}<br>
                <a href="{{ url_for('admin_delete_key', key_type='daily_keys', key_value=key) }}">Delete Key</a>
            </li>
            <hr>
        {% endfor %}
        </ul>
        <h3>Monthly Keys</h3>
        <ul>
        {% for key, info in keys_data.get('monthly_keys', {}).items() %}
            <li>
                <strong>{{ key }}</strong><br>
                Expiry: {{ info.expiry }}<br>
                In Use: {{ info.in_use }}<br>
                Last Used: {{ info.last_used }}<br>
                Owner: {{ info.owner }}<br>
                <a href="{{ url_for('admin_delete_key', key_type='monthly_keys', key_value=key) }}">Delete Key</a>
            </li>
            <hr>
        {% endfor %}
        </ul>
        <a href="{{ url_for('admin_dashboard') }}">Back to Dashboard</a>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <ul>
            {% for message in messages %}
              <li>{{ message }}</li>
            {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}
    """, keys_data=keys_data)

# Delete a key by type and key value
@app.route("/admin/delete/<key_type>/<key_value>")
@login_required
def admin_delete_key(key_type, key_value):
    if key_type in keys_data and key_value in keys_data[key_type]:
        del keys_data[key_type][key_value]
        save_keys(keys_data)
        flash("Key deleted successfully.")
    else:
        flash("Key not found.")
    return redirect(url_for("admin_list_keys"))

# ------------------------
# Run the app
# ------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
