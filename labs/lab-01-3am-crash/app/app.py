# app/app.py
from flask import Flask, jsonify
import threading, time

app = Flask(__name__)
_leak = []

@app.route("/health")
def health():
    return jsonify({"status":"ok"}), 200

@app.route("/leak")
def leak():
    # allocate memory in background to simulate leak
    def eater():
        while True:
            _leak.append("x" * 10_000_00)  # 1MB-ish chunk
            time.sleep(0.2)
    t = threading.Thread(target=eater, daemon=True)
    t.start()
    return "leak started\n", 200

@app.route("/")
def index():
    return "Lab App Running\n", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
