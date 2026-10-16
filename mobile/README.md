# triple-U 学生移动端

独立于 `frontend/` 的 Vue 3 + Vite 学生端，复用现有 FastAPI 后端的登录能力，并通过新增的 `/api/v1/mobile/*` 接口访问课程群、错题本和资源库。

## 本地运行

```powershell
cd D:\xunfei\triple-U\mobile
Copy-Item .env.example .env.local
cmd /c npm install
cmd /c npm run dev
```

默认访问 `http://localhost:5175`，后端默认是 `http://127.0.0.1:8000`。部署到其他域名时设置 `VITE_API_BASE_URL`，并在后端环境变量 `A3_CORS_ORIGINS` 中加入 H5 来源，多个来源用逗号分隔。

## 数据初始化

```powershell
cd D:\xunfei\triple-U
& 'D:\Anaconda3\envs\dxtorch\python.exe' scripts\seed_mobile_course_groups.py
```

脚本幂等创建人工智能课程协作群及演示成员。首次请求 `GET /api/v1/mobile/rooms` 也会执行相同的幂等初始化。

## 构建与 Capacitor

```powershell
cmd /c npm run test
cmd /c npm run build
cmd /c npm run cap:add:android
cmd /c npm run cap:sync
```

Android 可在 Windows 上继续使用 Android Studio 构建。iOS 工程通过 `npm run cap:add:ios` 创建，但最终签名与构建需要 macOS/Xcode。安装包构建时必须将 `VITE_API_BASE_URL` 指向手机能够访问的 HTTPS 后端，不能使用手机自身的 `127.0.0.1`。

H5 构建产物位于 `mobile/dist`，独立部署；不要复制到 `frontend/dist`，也不要加入 Electron 构建。
