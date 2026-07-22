# Railway uchun Dockerfile — LibreOffice va OpenCV ishonchli o'rnatiladi.
# Dockerfile mavjud bo'lsa, Railway uni Nixpacks o'rniga ishlatadi.

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HOME=/root

# Tizim paketlari:
#   libreoffice-writer  -> Word (.docx) -> PDF aylantirish (soffice /usr/bin ga tushadi)
#   libglib2.0-0, libgl1 -> OpenCV (skaner) import bo'lishi uchun
#   fonts-liberation    -> PDF shriftlari to'g'ri chiqishi uchun
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer \
      libglib2.0-0 \
      libgl1 \
      fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# main.py botni + web-serverni birga ishga tushiradi (Procfile bilan bir xil)
CMD ["python", "main.py"]
