FROM python:3.12-slim


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1


WORKDIR /app


COPY requirements.txt .


RUN pip install \
    --no-cache-dir \
    -r requirements.txt


# 创建非root用户
RUN groupadd \
        --system app \
    && useradd \
        --system \
        --gid app \
        --create-home app \
    && mkdir -p \
        /data/uploads \
        /data/results \
    && chown -R \
        app:app \
        /data


COPY \
    --chown=app:app \
    ./app \
    ./app


USER app


EXPOSE 8000


CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
