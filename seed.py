# seed.py
# Run this ONCE to:
#   1. Create all tables in PostgreSQL
#   2. Create the first admin (CA) user
#   3. Add the standard CA services (GST, ITR, Audit, ROC)
#
# Run with:  python seed.py

from database import engine, SessionLocal, Base
from models import User, Service
from auth import hash_password

# This line reads all models and creates their tables in PostgreSQL
# It's safe to run multiple times — it skips tables that already exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── Create admin user ──────────────────────────────────────────────────────────
existing_admin = db.query(User).filter(User.email == "admin@cadesk.com").first()
if not existing_admin:
    admin = User(
        name="CA Mehta",                        # change to your name
        email="admin@cadesk.com",               # change to your email
        password_hash=hash_password("Admin@123"),  # change this password immediately
        role="admin",
        phone="9876543210",                     # change to your phone
    )
    db.add(admin)
    print("[OK] Admin user created: admin@cadesk.com / Admin@123")
else:
    print("[INFO] Admin user already exists, skipping")

# ── Create standard CA services ───────────────────────────────────────────────
services = [
    {"name": "GST Registration",     "description": "New GST registration for businesses"},
    {"name": "GST Filing (Monthly)", "description": "GSTR-1 and GSTR-3B monthly filing"},
    {"name": "GST Filing (Annual)",  "description": "GSTR-9 annual return filing"},
    {"name": "ITR Filing",           "description": "Income tax return filing"},
    {"name": "Tax Audit (44AB)",     "description": "Tax audit under section 44AB"},
    {"name": "Statutory Audit",      "description": "Statutory audit for companies"},
    {"name": "ROC Filing",           "description": "Annual ROC / MCA compliance filing"},
    {"name": "Company Incorporation","description": "New Pvt Ltd or LLP registration"},
    {"name": "TDS Filing",           "description": "Quarterly TDS return filing"},
    {"name": "Bookkeeping",          "description": "Monthly accounts maintenance"},
]

for s in services:
    exists = db.query(Service).filter(Service.name == s["name"]).first()
    if not exists:
        db.add(Service(name=s["name"], description=s["description"]))
        print(f"[OK] Service added: {s['name']}")

db.commit()
db.close()

print("\n[SUCCESS] Database seeded successfully.")
print("[INFO] Login at /auth/login with: admin@cadesk.com / Admin@123")
print("[WARNING] Change the admin password immediately after first login!")