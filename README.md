# Nuvyoday 🌅

**A new sunrise for legacy IBM i (AS/400) systems.**

Nuvyoday helps you extract, understand, and document the business logic locked inside old green-screen IBM i applications so you can modernize with confidence.

It connects to your IBM i system, inventories source members (QCLSRC, QRPGSRC, etc.), builds mapping diagrams, and generates clean technical + functional specifications — eliminating the knowledge silos that stall migration projects.

## Deployment Model

| Mode | Purpose | Where it runs |
|------|---------|---------------|
| **Real product** | Full functionality + JT400 connection to IBM i | Customer premises via **iVistaar** on IIS (or local `python run.py`) |
| **Public UI Demo** | Show the look & feel only | Static site (Cloudflare Pages / any static host) – see `/demo` folder |

The real product is designed to run **inside the customer network** so it can reach internal IBM i systems securely. It is **not** meant to be a multi-tenant SaaS on the public internet.

## Features (Starter)

- Local Flask web application (runs on your machine)
- SQLite database for connections and harvested metadata
- Secure IBM i connection management (credentials encrypted at rest)
- JT400 (IBM Toolbox for Java) integration via JPype
- Connection test against real IBM i systems
- Clean, modern UI ready for expansion (inventory, source extraction, analysis)

## Requirements

- Python 3.11 or 3.12 recommended
- Java 8+ (required for JT400 / JPype)
- Network access to your IBM i (host servers must be running)

## Quick Start

```bash
# Clone
git clone https://github.com/vikkp/nuvyoday.git
cd nuvyoday

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and set a strong FLASK_SECRET_KEY

# Download JT400 (JTOpen)
# Place jt400.jar (or jtopen-*.jar) into the lib/ folder
# You can get the latest from: https://github.com/IBM/JTOpen/releases
# or Maven Central: net.sf.jt400:jt400

# Run
python run.py
```

Open your browser to: **http://127.0.0.1:5055**

## Project Structure

```
nuvyoday/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── config.py
│   ├── models.py            # SQLAlchemy models
│   ├── connection.py        # JT400 / JPype wrapper
│   ├── routes.py            # Web routes
│   ├── templates/
│   └── static/
├── demo/                   # Static UI for Cloudflare / public preview
├── data/                    # SQLite DB + future source storage
├── lib/                     # Place jt400.jar here
├── run.py
├── requirements.txt
└── README.md
```

## Roadmap

- [x] Starter project + connection management
- [ ] Library & source member inventory
- [ ] Source extraction (QCLSRC / QRPGSRC / QDDSSRC)
- [ ] Call graph & dependency mapping
- [ ] Automated technical + functional specification generation
- [ ] Diagram export
- [ ] Integration with iVistaar ecosystem

## Security Notes

- Passwords are encrypted at rest using Fernet (cryptography library).
- The encryption key is derived from `FLASK_SECRET_KEY`. Keep that secret.
- Never commit `.env` or the SQLite database.
- This tool is intended to run locally or in a controlled internal environment.

## Public UI Demo (Cloudflare / static)

A pure static version of the UI lives in the `/demo` folder. It uses the same colors and layout as the real app, with sample data and non-functional buttons.

**To deploy the demo on Cloudflare Pages:**

1. Create a new Pages project connected to this repo
2. Set **Build output directory** to `demo`
3. Leave Build command empty (or `echo "static demo"`)
4. Deploy

No Python, no Java, no JT400 — just HTML/CSS so anyone can see the product look-and-feel.

## License

Proprietary — ChaiiNCharge LLC / RayNu Technologies. All rights reserved.

---

Built with ❤️ for the teams still fighting green screens.
