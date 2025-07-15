# Backend

Backend cho ứng dụng chatbot sử dụng FastAPI và quản lý dependencies với uv.

## Yêu cầu hệ thống

- Python 3.13+
- uv (Python package manager)

## Cài đặt uv

Nếu chưa có uv, cài đặt bằng lệnh:

### macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows:

```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Hướng dẫn khởi động

### 1. Di chuyển vào thư mục backend

```bash
cd backend
```

### 2. Cài đặt dependencies

```bash
uv sync
```

### 3. Khởi động server development

```bash
fastapi dev main.py
```

### 4. Truy cập ứng dụng

- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Cấu trúc project

```
backend/
├── main.py              # Entry point của ứng dụng
├── pyproject.toml       # Cấu hình project và dependencies
├── uv.lock             # Lock file cho dependencies
├── routes/             # Các route endpoints
│   ├── __init__.py
│   ├── admin.py        # Admin routes
│   └── user.py         # User routes
└── README.md           # Tài liệu này
```
