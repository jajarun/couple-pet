FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 依赖先装，利用层缓存（cryptography/bcrypt 在 slim 上走预编译 wheel，无需编译器）
# PIP_INDEX_URL 可传国内镜像加速（如清华/阿里）；默认空 = 走官方 pypi，不影响 CI/本地
ARG PIP_INDEX_URL=""
COPY requirements.txt ./
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
