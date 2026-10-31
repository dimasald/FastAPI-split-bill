# Split Bill API

A secure REST API for splitting bills and tracking shared expenses among group members. Built with FastAPI, PostgreSQL, and JWT authentication, featuring strict financial validation, automated balance calculations, and a netting algorithm to minimize settlement transactions.

## Overview

This backend service allows users to create groups, invite members, record shared expenses, and settle debts. The core design focuses on data integrity and security: every expense requires mathematical validation to ensure the sum of splits equals the total amount, and access control prevents unauthorized data exposure (IDOR protection). Balances are calculated dynamically rather than stored, ensuring consistency.

## Key Features

- **Authentication**: JWT-based registration and login with Argon2 password hashing.
- **Group Management**: Role-based access control (Admin/Member), with protection against removing the last admin.
- **Expense Tracking**: Atomic transactions for creating expenses and their associated splits, with strict validation (`sum(splits) == amount`).
- **Dynamic Balances**: Real-time calculation of who owes whom, without storing redundant balances in the database.
- **Settlement Netting**: A greedy algorithm that suggests the minimum number of transfers required to settle all debts within a group.
- **Comprehensive Testing**: Over 35 test cases covering authentication, authorization, business logic, and edge cases.

## Tech Stack

- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Authentication**: python-jose (JWT), pwdlib (Argon2)
- **Testing**: Pytest, TestClient

## Prerequisites

- Python 3.11+
- PostgreSQL 14+

## Installation & Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/FastAPI-split-bill.git
   cd FastAPI-split-bill
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Create a `.env` file based on `.env.example` and provide your database credentials and a secure `SECRET_KEY`.

5. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://127.0.0.1:8000`. Interactive documentation is accessible at `/docs`.

## Usage

### Running Tests
Ensure the test environment is set up, then run:
```bash
pytest -v
```

### API Endpoints Overview
- **Auth**: `POST /auth/register`, `POST /auth/login`
- **Groups**: `POST /groups`, `GET /groups`, `POST /groups/{id}/invite`, `GET /groups/{id}/members`
- **Expenses**: `POST /groups/{id}/expenses`, `GET /groups/{id}/expenses`, `GET /groups/{id}/balances`
- **Settlements**: `POST /groups/{id}/settlements`, `GET /groups/{id}/settlements/suggested`

For detailed request/response schemas, refer to the Swagger UI at `/docs`.

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | Secret key for JWT signing | Yes |
| `ALGORITHM` | JWT algorithm (default: HS256) | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry in minutes (default: 30) | No |

## Note on Frontend

The backend architecture, database design, business logic, security auditing (IDOR, XSS, SQL injection prevention), and testing were entirely designed and implemented by me. The frontend UI (HTML/CSS/JS) was generated using AI as a productivity tool to accelerate visualization. The integration, validation, and security hardening between the frontend and backend were fully handled by me.

## License

This project is open-source and available under the MIT License.