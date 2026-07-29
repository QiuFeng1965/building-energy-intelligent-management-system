# 前端 Dockerfile — 多阶段构建
# 阶段1：构建 Vue3 静态资源
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制 package.json，利用缓存层
COPY package.json package-lock.json* ./

# 安装依赖
RUN npm install

# 复制源码并构建
COPY . .
RUN npm run build

# 阶段2：nginx 部署静态资源
FROM nginx:alpine

# 复制构建产物到 nginx 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 nginx 配置（处理 SPA 路由 + API 反向代理）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
