from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/api', defaults={'path': ''})
@app.route('/api/<path:path>')
def catch_all(path):
    return jsonify({"status": "ok", "message": "API endpoint not found"}), 404

if __name__ == '__main__':
    app.run()
