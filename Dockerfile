FROM python:3.12

# Install packages for OpenCV and Tesseract OCR
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

WORKDIR /app

COPY pyproject.toml poetry.lock* README.md LICENSE /app/
COPY src /app/src

RUN pip install poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi   # ohne --no-root

COPY . /app
CMD ["poetry", "run", "sentinel"]
