FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    GOOD_ENGINEERS_DATA_DIR=/data \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY .streamlit/config.toml /app/.streamlit/config.toml

COPY app.py .
COPY equipment_models_catalog.py .
# Logos / masthead hero (good_engineers_hero_masthead.png, etc.) — sans ce dossier l’UI en ligne ≠ poste local
COPY assets ./assets

# Échec du build si fichiers clés absents ou app.py trop ancien
RUN python -c "from pathlib import Path; t=Path('app.py').read_text(encoding='utf-8'); assert '_ensure_fleet_summary_df' in t, 'app.py obsolete'; assert Path('equipment_models_catalog.py').is_file(); assert Path('assets').is_dir()"

RUN mkdir -p /data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
