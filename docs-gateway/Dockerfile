FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid gateway --no-create-home gateway \
    && mkdir /data \
    && chown gateway:gateway /data
WORKDIR /app
COPY --chown=gateway:gateway app/ /app/
USER gateway
EXPOSE 8080
CMD ["python", "/app/server.py"]
