# Sử dụng image Python nhẹ
FROM python:3.10-slim

WORKDIR /app

# Copy file requirements và cài đặt thư viện trước để tận dụng cache của Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code backend vào container
COPY . .

# Mở port (Giả sử app.py của bạn chạy ở port 5000, nếu khác thì đổi lại nhé)
EXPOSE 5000

# Chạy ứng dụng
CMD ["python", "app.py"]