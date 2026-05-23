# PTC Portal - Backend

This is the FastAPI backend for the PTC Portal application.

## 🚀 Tech Stack

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT Tokens
- **Scraping**: Selenium / Requests for GST scraping tasks

## 📦 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL server

### Installation

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it (optional but recommended):
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Environment Variables:
   - Create a `.env` file based on `.env.example`
   - Configure your database URI and other sensitive tokens.

### Running the Server

Start the development server with auto-reload enabled:

```bash
uvicorn main:app --reload
```

The API will be accessible at `http://127.0.0.1:8000`. 
Interactive API documentation (Swagger UI) is automatically available at `http://127.0.0.1:8000/docs`.
