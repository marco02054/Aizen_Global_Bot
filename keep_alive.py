from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def index():
    return "Alive"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"An error occurred: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == '__main__':
    keep_alive()
