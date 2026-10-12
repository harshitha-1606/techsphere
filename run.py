import os

from backend.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    try:
        if os.environ.get("FLASK_DEBUG") == "1":
            raise ImportError
        from waitress import serve  # production-grade WSGI server (pip install -r requirements.txt)
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        print("NOTE: waitress not installed (or FLASK_DEBUG=1) - using Flask's development server.")
        app.run(host=host, port=port, threaded=True)
