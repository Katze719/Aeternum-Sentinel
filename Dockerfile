# Basis-Image mit Python 3.10
FROM python:3.12

# Installiere benötigte Pakete für OpenCV & Tesseract OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    libtesseract-dev \
    libasound2-dev \
    libavcodec-extra \
    libavformat-dev \
    libswscale-dev \
    libxext6 \
    libxrender-dev \
    libsm6 \
    ffmpeg \
    locales \
    && rm -rf /var/lib/apt/lists/*

RUN echo "de_DE.UTF-8 UTF-8" >> /etc/locale.gen; \
    locale-gen

# Setze das Arbeitsverzeichnis
WORKDIR /app

# 1) Projekt-Metadaten + Source ins Image legen
COPY pyproject.toml poetry.lock* README.md LICENSE /app/
COPY src /app/src

# 2) Poetry installieren & dein Paket inklusive Skript setup-en
RUN pip install poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi   # ohne --no-root

# 3) Restliche Dateien (Tests, CI-Configs …) nachziehen – optional
COPY . /app
CMD ["poetry", "run", "sentinel"]
