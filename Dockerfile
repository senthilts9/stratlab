# ── build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /src

# Copy only what's needed to install dependencies + your package
COPY requirements.txt setup.py ./
RUN pip install --prefix=/install -r requirements.txt \
 && pip install --prefix=/install -e .

# ── runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Bring in the installed deps + your package
COPY --from=build /install /usr/local

# Copy the rest of your application
COPY . /app

# Run Streamlit
CMD ["streamlit", "run", "app/main.py", "--server.port", "8501"]
