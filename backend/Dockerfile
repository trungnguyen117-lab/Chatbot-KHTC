FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# --- TỐI ƯU HÓA BẮT ĐẦU TỪ ĐÂY ---

# 1. Chỉ copy file định nghĩa thư viện trước
COPY pyproject.toml ./ 
# Nếu bạn dùng requirements.txt, hãy copy nó: COPY requirements.txt ./

# 2. Cài đặt các gói hệ thống (không thay đổi)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Cài đặt thư viện Python. Lớp này sẽ được cache nếu pyproject.toml không đổi
RUN uv sync

# 4. SAU KHI CÀI XONG, mới copy toàn bộ code ứng dụng
COPY . .

# --- KẾT THÚC TỐI ƯU HÓA ---

EXPOSE 8000

# Start command
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]