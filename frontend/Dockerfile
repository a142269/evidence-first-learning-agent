# Multi-stage build: 先构建 Vue 静态资产，再用 nginx serve

# ============================================================
# Stage 1: 构建静态资产
# ============================================================
FROM node:20-alpine AS builder

WORKDIR /app

# 利用 layer cache：package.json 先 COPY
COPY package.json package-lock.json* ./

# 用 npm ci 走 lock 文件，可重现且更快
RUN npm ci --no-audit --no-fund

# 拷源码 + 构建
COPY . .

# 通过 build arg 控制 API 基址：
#   - 默认空字符串 → 前端走同源相对路径 → 浏览器走 window.location.origin → nginx 反代到 backend
#   - 也可传 http://192.168.x.x:8000 等绝对地址（远程后端场景）
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ============================================================
# Stage 2: nginx serve dist/
# ============================================================
FROM nginx:1.27-alpine

# 拷构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 自定义 nginx 配置：SPA 路由 fallback 到 index.html + API 反代
RUN printf '%s\n' \
  'server {' \
  '    listen 5173;' \
  '    server_name localhost;' \
  '    root /usr/share/nginx/html;' \
  '    index index.html;' \
  '' \
  '    # Vue Router 历史模式：所有未命中静态资源 fallback 到 index.html' \
  '    location / {' \
  '        try_files $uri $uri/ /index.html;' \
  '    }' \
  '' \
  '    # API 反代到后端容器（compose service name = backend）' \
  '    location /api/ {' \
  '        # backend 容器重建后 IP 会变化。用 Docker 内置 DNS 动态解析，' \
  '        # 避免 nginx 在启动时缓存旧 IP 而持续返回 502。' \
  '        resolver 127.0.0.11 valid=10s ipv6=off;' \
  '        set $backend_upstream http://backend:8000;' \
  '        proxy_pass $backend_upstream;' \
  '        proxy_http_version 1.1;' \
  '        proxy_set_header Upgrade $http_upgrade;' \
  '        proxy_set_header Connection "upgrade";' \
  '        proxy_set_header Host $host;' \
  '        proxy_set_header X-Real-IP $remote_addr;' \
  '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
  '        # SSE 流式对话：禁用 buffering + 长超时' \
  '        proxy_buffering off;' \
  '        proxy_cache off;' \
  '        proxy_read_timeout 600s;' \
  '        proxy_send_timeout 600s;' \
  '        chunked_transfer_encoding off;' \
  '    }' \
  '' \
  '    # 静态资产强缓存（hash 文件名）' \
  '    location /assets/ {' \
  '        expires 1y;' \
  '        add_header Cache-Control "public, immutable";' \
  '    }' \
  '' \
  '    # 健康端点（compose healthcheck / docker_smoke 用）' \
  '    location /healthz {' \
  '        access_log off;' \
  '        return 200 "ok\\n";' \
  '        add_header Content-Type text/plain;' \
  '    }' \
  '}' \
  > /etc/nginx/conf.d/default.conf

EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:5173/healthz > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
