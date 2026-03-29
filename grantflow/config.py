import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

ENV = os.getenv("GRANTFLOW_ENV", "development")
DATABASE_URL = os.getenv("GRANTFLOW_DATABASE_URL", "sqlite:///grantflow.db")
HOST = os.getenv("GRANTFLOW_HOST", "0.0.0.0")
PORT = int(os.getenv("GRANTFLOW_PORT", "8001"))

GRANTS_GOV_XML_URL = "https://www.grants.gov/xml-extract"
GRANTS_GOV_REST_API_BASE = os.getenv(
    "GRANTS_GOV_REST_API_BASE", "https://api.grants.gov/v1/api"
)
GRANTS_GOV_USE_REST = os.getenv("GRANTS_GOV_USE_REST", "").lower() in (
    "1",
    "true",
    "yes",
)
USASPENDING_API_BASE = "https://api.usaspending.gov/api/v2"
SBIR_AWARDS_CSV_URL = "https://data.www.sbir.gov/awarddatapublic/award_data.csv"
SBIR_SOLICITATIONS_API = "https://api.www.sbir.gov/public/api/solicitations"
SAM_GOV_API_KEY = os.getenv("SAM_GOV_API_KEY", "")  # empty = use public (10 req/day)
SAM_GOV_API_BASE = os.getenv("SAM_GOV_API_BASE", "https://api.sam.gov/opportunities/v2")

# State scraper config
STATE_SCRAPER_BATCH_SIZE = int(os.getenv("STATE_SCRAPER_BATCH_SIZE", "100"))
STATE_SCRAPER_REQUEST_DELAY = float(os.getenv("STATE_SCRAPER_REQUEST_DELAY", "1.0"))

# SMTP email config (for digest alerts)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@grantflow.io")

# Stripe billing config
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER_ID = os.getenv("STRIPE_PRICE_STARTER_ID", "")
STRIPE_PRICE_GROWTH_ID = os.getenv("STRIPE_PRICE_GROWTH_ID", "")
