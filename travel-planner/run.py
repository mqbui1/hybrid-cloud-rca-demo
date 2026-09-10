"""Entrypoint: selects which agent service to run via APP_SERVICE env var."""
import os
import importlib

service = os.environ.get("APP_SERVICE", "orchestrator")
module = importlib.import_module(f"{service}.app")
app = module.app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
