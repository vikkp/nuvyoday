#!/usr/bin/env python3
"""Nuvyoday entry point."""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("NUVYODAY_PORT", 5055))
    print(f"\n🌅  Nuvyoday is starting...")
    print(f"    Open http://127.0.0.1:{port} in your browser\n")
    app.run(host="127.0.0.1", port=port, debug=True)
