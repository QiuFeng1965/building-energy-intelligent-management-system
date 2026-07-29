# 后端 Dockerfile — 多阶段构建
# 基础镜像：Python 3.11 slim（体积小，含 pip）
FROM python:3.11-slim AS backend

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 生成 .pyc 缓存和缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖（gcc 用于编译 bcrypt/psycopg2 等需要编译的包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements.txt，利用 Docker 缓存层加速构建
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令：uvicorn 监听 8000
# 使用 app.main:app（新分层架构入口）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
