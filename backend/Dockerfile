# 基础镜像 tag 可覆盖：默认 3.13-slim；国内/离线机器可传本地已缓存的 tag（如 3.12-slim）避免拉 Docker Hub
ARG PYTHON_TAG=3.13-slim
FROM python:${PYTHON_TAG}

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
