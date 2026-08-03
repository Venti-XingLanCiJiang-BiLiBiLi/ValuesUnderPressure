# ============================================================================
# VUP 前端镜像（多阶段构建）
# ----------------------------------------------------------------------------
# 阶段 1: Node 构建 Vite 产物
# 阶段 2: Nginx 托管静态文件 + 反代 /api 到后端容器
# 构建上下文为【仓库根目录】：docker compose build frontend
# 可选构建参数 VITE_API_BASE_URL：默认 /api（同源反代），前后端分离时覆盖。
# ============================================================================

# ---- 阶段 1: 构建 ----
FROM node:22-alpine AS build

WORKDIR /app

# 可选：前端 API 地址（默认 /api 同源反代，无需修改）
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# 先复制依赖清单，利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 复制源码并构建（含类型检查）
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2: 运行 ----
FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
