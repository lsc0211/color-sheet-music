FROM python:3.11-slim

# 安装 Verovio 所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建上传和输出目录
RUN mkdir -p uploads outputs

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 10000

# 使用 gunicorn 启动 Flask 应用
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120"]