# 多阶段构建 - 生产环境优化
# 支持 linux/amd64 和 linux/arm64
FROM --platform=$BUILDPLATFORM python:3.11-slim AS builder

# 构建参数
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libgmp-dev \
    libmpfr-dev \
    libmpc-dev \
    ocl-icd-opencl-dev \
    opencl-headers \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements-base.txt requirements-base.txt
COPY requirements-gpu.txt requirements-gpu.txt
COPY requirements-dev.txt requirements-dev.txt
COPY requirements.txt requirements.txt

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# 生产阶段
FROM --platform=$TARGETPLATFORM python:3.11-slim AS production

# 标签信息
LABEL maintainer="BTC Project" \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="BTC Collision Engine" \
    org.label-schema.description="Bitcoin Address Collision Detection Engine" \
    org.label-schema.version="${VERSION}" \
    org.label-schema.build-date="${BUILD_DATE}" \
    org.label-schema.vcs-ref="${VCS_REF}" \
    org.label-schema.vcs-url="https://github.com/your-repo/btc-collision-engine"

# 运行时参数
# cpu 或 gpu（注意：此 ARG 在 production stage 中未被引用，保留供后续扩展）
ARG RUN_MODE="cpu"

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/opt/btc-collision-engine \
    DATA_DIR=/opt/btc-collision-engine/data_logs \
    LOG_DIR=/opt/btc-collision-engine/logs \
    MONITOR_DIR=/opt/btc-collision-engine/monitoring_data

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础依赖
    curl \
    tini \
    # OpenCL运行时（GPU模式需要）
    ocl-icd-libopencl1 \
    # GPU驱动（根据实际需要选择）
    # NVIDIA
    # nvidia-opencl-icd \
    # AMD
    # mesa-opencl-icd \
    # Intel
    # intel-opencl-icd \
    # 数学库
    libgmp10 \
    libmpfr6 \
    # 清理
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建工作目录
RUN mkdir -p ${APP_HOME} ${DATA_DIR} ${LOG_DIR} ${MONITOR_DIR}
WORKDIR ${APP_HOME}

# 复制应用代码
COPY --chown=1000:1000 . .

# 创建数据目录（如果不存在）
RUN mkdir -p data_logs monitoring_data logs

# 设置目录权限
RUN chmod 750 ${DATA_DIR} ${LOG_DIR} ${MONITOR_DIR} \
    && chmod 750 data_logs monitoring_data logs

# 创建非root用户并切换
RUN groupadd -r btc-engine && useradd -r -g btc-engine -d ${APP_HOME} -s /sbin/nologin btc-engine \
    && chown -R btc-engine:btc-engine ${APP_HOME}

# 切换到非 root 用户运行（安全加固）
USER btc-engine

# 健康检查
HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
    CMD python -m src.utils.health_check --quiet || exit 1

# 暴露端口（如果有Web监控界面）
# EXPOSE 8080

# 使用tini作为init系统
ENTRYPOINT ["/usr/bin/tini", "--"]

# 默认命令
CMD ["python", "key_collision_cli.py", "--help"]

# GPU模式入口点
# ENTRYPOINT ["/usr/bin/tini", "--", "python", "key_collision_cli.py", "--mode", "random", "--checkpoint"]
