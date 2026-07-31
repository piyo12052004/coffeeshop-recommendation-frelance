FROM python:3.14-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Working Directory
WORKDIR /app

# Install dependency Linux
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    chromium \
    chromium-driver \
    curl \
    wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Clone Repository
RUN git clone https://github.com/nadialuthfia10/coffeeshop-recommendation.git .

# Membuat requirements.txt
RUN cat <<'EOF' > requirements.txt
attrs==26.1.0
Authlib==1.7.2
blinker==1.9.0
certifi==2026.7.22
cffi==2.1.0
charset-normalizer==3.4.9
click==8.4.2
cryptography==49.0.0
et_xmlfile==2.0.0
Flask==3.1.3
Flask-SQLAlchemy==3.1.1
h11==0.16.0
idna==3.18
itsdangerous==2.2.0
Jinja2==3.1.6
joblib==1.5.3
joserfc==1.7.4
MarkupSafe==3.0.3
mysql-connector-python==26.7.0
narwhals==2.24.0
numpy==2.5.1
openpyxl==3.1.5
outcome==1.3.0.post0
packaging==26.2
pandas==3.0.5
pycparser==3.0
PyMySQL==1.2.0
PySocks==1.7.1
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
requests==2.34.2
scikit-learn==1.9.0
scipy==1.18.0
selenium==4.46.0
six==1.17.0
sniffio==1.3.1
sortedcontainers==2.4.0
SQLAlchemy==2.0.51
threadpoolctl==3.6.0
trio==0.33.0
trio-websocket==0.12.2
typing_extensions==4.16.0
urllib3==2.7.0
webdriver-manager==4.1.2
websocket-client==1.9.0
Werkzeug==3.1.8
wsproto==1.3.2
EOF

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask
EXPOSE 5000

# Jalankan Flask
CMD ["python", "app.py"]