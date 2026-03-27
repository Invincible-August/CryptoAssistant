# CryptoAssistant 部署指南

> 本文档面向零基础用户，分别说明如何在 **Windows** 和 **Linux (Ubuntu/Debian)** 上从零开始部署本项目，直到前后端均可正常运行。请严格按照步骤顺序操作。

---

## 目录

- [项目架构总览](#项目架构总览)
- [所需软件清单](#所需软件清单)
- [第一部分：Windows 部署](#第一部分windows-部署)
  - [1. 安装 Python 3.12+](#1-安装-python-312)
  - [2. 安装 Node.js 20+](#2-安装-nodejs-20)
  - [3. 安装 PostgreSQL 16+](#3-安装-postgresql-16)
  - [4. 安装 Redis（Windows 替代方案）](#4-安装-rediswindows-替代方案)
  - [5. 安装 Git（可选但推荐）](#5-安装-git可选但推荐)
  - [6. 获取项目代码](#6-获取项目代码)
  - [7. 配置环境变量](#7-配置环境变量)
  - [8. 创建数据库](#8-创建数据库)
  - [9. 启动 Redis](#9-启动-redis)
  - [10. 安装后端依赖并初始化](#10-安装后端依赖并初始化)
  - [11. 启动后端](#11-启动后端)
  - [12. 安装前端依赖并启动](#12-安装前端依赖并启动)
  - [13. 验证部署](#13-验证部署)
  - [Windows 快捷方式：一键脚本](#windows-快捷方式一键脚本)
- [第二部分：Linux (Ubuntu/Debian) 部署](#第二部分linux-ubuntudebian-部署)
  - [1. 更新系统包](#1-更新系统包)
  - [2. 安装 Python 3.12+](#2-安装-python-312)
  - [3. 安装 Node.js 20+](#3-安装-nodejs-20-1)
  - [4. 安装 PostgreSQL 16+](#4-安装-postgresql-16-1)
  - [5. 安装 Redis 7+](#5-安装-redis-7)
  - [6. 安装 Git](#6-安装-git)
  - [7. 获取项目代码](#7-获取项目代码)
  - [8. 配置环境变量](#8-配置环境变量)
  - [9. 创建数据库](#9-创建数据库-1)
  - [10. 安装后端依赖并初始化](#10-安装后端依赖并初始化-1)
  - [11. 启动后端](#11-启动后端-1)
  - [12. 安装前端依赖并启动](#12-安装前端依赖并启动-1)
  - [13. 验证部署](#13-验证部署-1)
- [常见问题排查](#常见问题排查)
- [端口速查表](#端口速查表)

---

## 项目架构总览

```
┌──────────────────────────────────────────────────┐
│                  浏览器 (用户)                      │
│              http://localhost:5173                │
│                      │                           │
│                      ▼                           │
│  ┌─────────────────────────────────────┐         │
│  │      前端 (React + Vite)            │         │
│  │      端口: 5173                     │         │
│  │      /api/* 自动代理到后端           │         │
│  └──────────────┬──────────────────────┘         │
│                 │ HTTP / WebSocket                │
│                 ▼                                 │
│  ┌─────────────────────────────────────┐         │
│  │      后端 (FastAPI + Uvicorn)       │         │
│  │      端口: 8000                     │         │
│  └───────┬─────────────┬───────────────┘         │
│          │             │                         │
│          ▼             ▼                         │
│  ┌────────────┐ ┌────────────┐                   │
│  │ PostgreSQL │ │   Redis    │                   │
│  │ 端口: 5432 │ │ 端口: 6379 │                   │
│  └────────────┘ └────────────┘                   │
└──────────────────────────────────────────────────┘
```

## 所需软件清单

| 软件 | 版本要求 | 用途 |
|------|---------|------|
| **Python** | 3.12+ | 后端运行环境 |
| **Node.js** | 20+ | 前端构建/开发服务器 |
| **PostgreSQL** | 16+ | 主数据库 |
| **Redis** | 7+（Windows 可用 Memurai） | 缓存与消息队列 |
| **Git** | 任意版本 | 获取项目代码（可选） |

---

# 第一部分：Windows 部署

> 以下所有操作在 Windows 10/11 上测试通过。

## 1. 安装 Python 3.12+

**下载地址**：https://www.python.org/downloads/

### 操作步骤

1. 打开上方链接，点击「Download Python 3.12.x」按钮下载安装包
2. 双击运行安装包
3. **重要**：勾选页面底部的 ✅ **「Add python.exe to PATH」**（不勾选后续所有命令都无法识别 python）
4. 点击「Install Now」等待安装完成
5. 安装完成后点击「Close」

### 验证安装

打开 **命令提示符**（按 `Win + R`，输入 `cmd`，回车）：

```
python --version
```

应输出类似 `Python 3.12.x`。如果提示「不是内部或外部命令」，说明 PATH 未配置成功，需要重新安装并勾选 PATH 选项。

同时验证 pip（Python 包管理器）：

```
pip --version
```

应输出类似 `pip 24.x.x from ...`。

---

## 2. 安装 Node.js 20+

**下载地址**：https://nodejs.org/

### 操作步骤

1. 打开上方链接，下载 **LTS（长期支持版）** 安装包（推荐 `.msi` 格式）
2. 双击运行，一路点击「Next」即可（默认设置会自动添加到 PATH）
3. 安装完成后点击「Finish」

### 验证安装

打开新的命令提示符窗口：

```
node --version
```

应输出类似 `v20.x.x` 或更高版本。

```
npm --version
```

应输出类似 `10.x.x`。

---

## 3. 安装 PostgreSQL 16+

**下载地址**：https://www.postgresql.org/download/windows/

### 操作步骤

1. 打开上方链接，点击「Download the installer」进入 EDB 安装程序页面
2. 选择最新版本（16+），下载 Windows x86-64 安装包
3. 双击运行安装程序
4. 安装路径保持默认即可
5. **设置超级用户密码**：安装过程中会要求设置 `postgres` 用户的密码，**请牢记此密码**（后续配置需要用到）
6. **端口**：保持默认 `5432`
7. **区域设置**：保持默认
8. 点击「Next」完成安装

### 验证安装

打开新的命令提示符窗口：

```
psql -U postgres
```

输入安装时设置的密码，看到 `postgres=#` 提示符即表示连接成功。输入 `\q` 退出。

> **注意**：如果提示「psql 不是内部或外部命令」，需要手动将 PostgreSQL 的 `bin` 目录添加到系统 PATH。默认路径一般为 `C:\Program Files\PostgreSQL\16\bin`。
>
> 添加方法：右键「此电脑」→「属性」→「高级系统设置」→「环境变量」→ 在系统变量的 `Path` 中添加上述路径 → 确定 → **重新打开命令提示符**。

---

## 4. 安装 Redis（Windows 替代方案）

Redis 官方不直接支持 Windows，有以下几种方式可选：

### 方案 A：Memurai（推荐，最简单）

**下载地址**：https://www.memurai.com/get-memurai

1. 下载 Memurai 免费版安装包
2. 双击安装，一路默认即可
3. 安装完成后 Memurai 会作为 Windows 服务自动启动，**无需手动操作**

验证 Memurai 是否正常运行：

```
memurai-cli ping
```

应输出 `PONG`。

> **注意**：Memurai 的命令行工具叫 `memurai-cli`，不是 `redis-cli`。两者用法完全一致，只是可执行文件名不同。如果提示「不是内部或外部命令」，需要将 Memurai 安装目录添加到系统 PATH（默认安装路径：`C:\Program Files\Memurai\`）。

### 方案 B：通过 WSL2 安装 Redis（如果你已有 WSL2）

```bash
# 在 WSL2 终端中
sudo apt update
sudo apt install redis-server -y
sudo service redis-server start
```

验证：在 WSL2 终端中执行 `redis-cli ping`，应输出 `PONG`。

> 使用 WSL2 方案时，Windows 侧的程序可以直接通过 `localhost:6379` 连接到 WSL2 中的 Redis，无需额外配置。

### 方案 C：使用微软维护的 Windows 版 Redis

**下载地址**：https://github.com/tporadowski/redis/releases

1. 下载最新的 `.msi` 安装包
2. 安装时勾选「Add the Redis installation folder to the PATH」
3. 安装完成后 Redis 会作为 Windows 服务自动启动

验证：打开命令提示符：

```
redis-cli ping
```

应输出 `PONG`。

### 各方案验证命令对照

| 方案 | 验证命令 | 预期输出 |
|------|---------|---------|
| 方案 A (Memurai) | `memurai-cli ping` | `PONG` |
| 方案 B (WSL2) | 在 WSL2 终端中执行 `redis-cli ping` | `PONG` |
| 方案 C (tporadowski) | `redis-cli ping` | `PONG` |

---

## 5. 安装 Git（可选但推荐）

**下载地址**：https://git-scm.com/download/win

1. 下载安装包，双击运行
2. 所有选项保持默认，一路「Next」即可
3. 安装完成后，打开新终端，输入 `git --version` 验证

---

## 6. 获取项目代码

如果你已经有项目文件夹，跳过此步。否则：

```
git clone <你的仓库地址> TradingAgent
cd TradingAgent
```

或者直接解压项目压缩包到某个目录，例如 `D:\otherProject\TradingAgent`。

---

## 7. 配置环境变量

在项目根目录下，复制环境变量模板：

```
copy .env.example .env
```

用记事本或 VS Code 打开 `.env` 文件，**必须修改以下配置**：

```ini
# 数据库连接 —— 将 "postgres" 密码替换为你在步骤3中设置的 PostgreSQL 密码
DATABASE_URL=postgresql+asyncpg://postgres:你的PostgreSQL密码@localhost:5432/crypto_assistant

# Redis 连接 —— 如果 Redis 没有设密码（默认情况），保持原样即可
REDIS_URL=redis://localhost:6379/0
```

其他配置可暂时保持默认，后续根据需要修改。

---

## 8. 创建数据库

打开命令提示符，连接 PostgreSQL：

```
psql -U postgres
```

输入你的 PostgreSQL 密码后，在 `postgres=#` 提示符中执行：

```sql
CREATE DATABASE crypto_assistant;
```

应看到 `CREATE DATABASE` 确认信息。然后退出：

```
\q
```

---

## 9. 启动 Redis

如果你使用的是 Memurai 或 Windows 服务版 Redis，它已经在后台自动运行了，跳过此步。

如果需要手动启动（仅方案 C 未设为服务时需要）：

```
redis-server
```

> **注意**：手动启动时这个窗口需要保持打开，后续操作请另开新的命令提示符窗口。
>
> 如果使用 **方案 A (Memurai)**，可通过 `Win + R` → 输入 `services.msc` → 查找 **Memurai** 服务确认其状态为「正在运行」。

---

## 10. 安装后端依赖并初始化

### 10.1 安装 Python 依赖

打开命令提示符，进入项目目录：

```
cd D:\otherProject\TradingAgent\backend
pip install -r requirements.txt
```

这一步会自动安装所有后端需要的 Python 库，耐心等待安装完成。

> **如果安装速度很慢**，可以使用国内镜像源加速：
> ```
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 10.2 创建管理员账户

回到项目根目录：

```
cd D:\otherProject\TradingAgent
python scripts/create_admin.py
```

应看到 `[成功] 管理员账户创建成功: admin`。

### 10.3 导入示例数据

```
python scripts/seed_demo_data.py
```

应看到多条 `[成功]` 信息，表示示例数据已导入。

---

## 11. 启动后端

```
cd D:\otherProject\TradingAgent\backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

看到类似以下输出说明启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx] using StatReload
```

> **注意**：这个窗口需要保持打开。后续操作请另开新的命令提示符窗口。

---

## 12. 安装前端依赖并启动

**打开一个全新的命令提示符窗口**：

```
cd D:\otherProject\TradingAgent\frontend
npm install
npm run dev
```

看到类似以下输出说明启动成功：

```
  VITE v6.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

## 13. 验证部署

打开浏览器，依次访问以下地址确认一切正常：

| 地址 | 预期结果 |
|------|---------|
| http://localhost:5173 | 看到前端登录页面 |
| http://localhost:8000/docs | 看到 FastAPI 自动生成的 API 文档（Swagger UI） |
| http://localhost:8000/health | 看到 `{"status":"ok",...}` JSON 响应 |

**默认登录账号**：
- 用户名：`admin`
- 密码：`admin123456`

---

## Windows 快捷方式：一键脚本

项目提供了 Windows 批处理脚本，位于 `scripts/` 目录：

| 脚本 | 用途 |
|------|------|
| `scripts\init_project.bat` | 首次使用：一键安装所有依赖 + 创建管理员 + 导入示例数据 |
| `scripts\start_backend.bat` | 启动后端服务 |
| `scripts\start_frontend.bat` | 启动前端服务（需另开窗口运行） |

**首次部署可以简化为**：

1. 完成步骤 1-9（安装软件、配置 `.env`、创建数据库、启动 Redis）
2. 双击运行 `scripts\init_project.bat`（自动安装依赖和初始化数据）
3. 双击运行 `scripts\start_backend.bat`
4. 双击运行 `scripts\start_frontend.bat`
5. 浏览器访问 http://localhost:5173

---

# 第二部分：Linux (Ubuntu/Debian) 部署

> 以下以 Ubuntu 22.04 / 24.04 为例，其他 Debian 系发行版操作类似。

## 1. 更新系统包

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 2. 安装 Python 3.12+

Ubuntu 22.04 自带 Python 3.10，需要通过 deadsnakes PPA 安装更新版本：

```bash
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev -y
```

安装 pip：

```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12
```

### 验证安装

```bash
python3.12 --version
# 应输出: Python 3.12.x

pip3 --version
# 应输出: pip 24.x.x from ...
```

### 设置别名（可选，方便后续使用）

```bash
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1
```

---

## 3. 安装 Node.js 20+

使用 NodeSource 官方仓库安装：

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
```

### 验证安装

```bash
node --version
# 应输出: v20.x.x

npm --version
# 应输出: 10.x.x
```

---

## 4. 安装 PostgreSQL 16+

```bash
# 添加 PostgreSQL 官方仓库
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# 安装 PostgreSQL 16
sudo apt install postgresql-16 -y
```

### 启动并设置开机自启

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 设置 postgres 用户密码

```bash
sudo -u postgres psql
```

在 `postgres=#` 提示符中执行：

```sql
ALTER USER postgres WITH PASSWORD '你想设置的密码';
```

然后退出：

```
\q
```

### 验证安装

```bash
psql -U postgres -h localhost
# 输入刚设置的密码，看到 postgres=# 提示符即成功
# 输入 \q 退出
```

> **如果连接报错 `peer authentication failed`**，需要修改认证方式：
> ```bash
> sudo nano /etc/postgresql/16/main/pg_hba.conf
> ```
> 找到 `local all postgres peer` 这一行，将 `peer` 改为 `md5`，保存后重启：
> ```bash
> sudo systemctl restart postgresql
> ```

---

## 5. 安装 Redis 7+

```bash
sudo apt install redis-server -y
```

### 启动并设置开机自启

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 验证安装

```bash
redis-cli ping
# 应输出: PONG
```

---

## 6. 安装 Git

```bash
sudo apt install git -y
```

---

## 7. 获取项目代码

```bash
cd /opt
sudo git clone <你的仓库地址> TradingAgent
sudo chown -R $USER:$USER TradingAgent
cd TradingAgent
```

或者将项目文件上传到服务器的 `/opt/TradingAgent` 目录。

---

## 8. 配置环境变量

```bash
cd /opt/TradingAgent
cp .env.example .env
nano .env
```

**必须修改以下配置**：

```ini
# 数据库连接 —— 替换为你的 PostgreSQL 密码
DATABASE_URL=postgresql+asyncpg://postgres:你的PostgreSQL密码@localhost:5432/crypto_assistant

# Redis 连接 —— 默认无密码，保持即可
REDIS_URL=redis://localhost:6379/0
```

按 `Ctrl + O` 保存，`Ctrl + X` 退出 nano 编辑器。

---

## 9. 创建数据库

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE crypto_assistant;
\q
```

---

## 10. 安装后端依赖并初始化

### 10.1 创建 Python 虚拟环境（推荐）

```bash
cd /opt/TradingAgent
python3.12 -m venv venv
source venv/bin/activate
```

> 激活虚拟环境后，终端提示符前会出现 `(venv)` 标识。
> 后续每次启动后端前，都需要先执行 `source venv/bin/activate` 激活虚拟环境。

### 10.2 安装 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

> **如果安装速度很慢**，可以使用国内镜像源加速：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 10.3 创建管理员账户

```bash
cd /opt/TradingAgent
python scripts/create_admin.py
```

应看到 `[成功] 管理员账户创建成功: admin`。

### 10.4 导入示例数据

```bash
python scripts/seed_demo_data.py
```

应看到多条 `[成功]` 信息。

---

## 11. 启动后端

```bash
cd /opt/TradingAgent/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

看到以下输出说明启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

> **提示**：可以使用 `nohup` 或 `screen` / `tmux` 让后端在后台持续运行：
> ```bash
> # 方式一：nohup
> nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
>
> # 方式二：tmux（推荐）
> sudo apt install tmux -y
> tmux new -s backend
> cd /opt/TradingAgent/backend
> source ../venv/bin/activate
> uvicorn app.main:app --host 0.0.0.0 --port 8000
> # 按 Ctrl+B 然后按 D 退出 tmux（服务继续运行）
> # 重新连接: tmux attach -t backend
> ```

---

## 12. 安装前端依赖并启动

**打开一个新的终端窗口**（或使用另一个 tmux 会话）：

```bash
cd /opt/TradingAgent/frontend
npm install
npm run dev
```

看到以下输出说明启动成功：

```
  VITE v6.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

> **如果是远程服务器**，需要添加 `--host` 参数使外部可访问：
> ```bash
> npm run dev -- --host 0.0.0.0
> ```

---

## 13. 验证部署

| 地址 | 预期结果 |
|------|---------|
| http://localhost:5173（或 http://服务器IP:5173） | 看到前端登录页面 |
| http://localhost:8000/docs | 看到 Swagger API 文档 |
| http://localhost:8000/health | 看到 `{"status":"ok",...}` |

**默认登录账号**：
- 用户名：`admin`
- 密码：`admin123456`

---

## Linux 快捷方式：Shell 脚本

项目提供了 Linux/macOS 启动脚本，位于 `scripts/` 目录：

| 脚本 | 用途 |
|------|------|
| `scripts/start_backend.sh` | 启动后端服务 |
| `scripts/start_frontend.sh` | 启动前端服务 |

首次使用需要添加执行权限：

```bash
chmod +x scripts/start_backend.sh scripts/start_frontend.sh
```

然后分别在两个终端窗口中运行：

```bash
# 终端1 — 启动后端
./scripts/start_backend.sh

# 终端2 — 启动前端
./scripts/start_frontend.sh
```

---

# 常见问题排查

### Q1：`python` 命令提示「不是内部或外部命令」

**Windows**：安装 Python 时没有勾选「Add to PATH」。解决方案：
1. 重新运行 Python 安装程序，选择「Modify」，确保勾选 PATH
2. 或者手动添加 Python 安装路径到系统 PATH（通常在 `C:\Users\你的用户名\AppData\Local\Programs\Python\Python312\`）

**Linux**：使用 `python3.12` 替代 `python` 命令，或配置 alternatives（参见上文）。

### Q2：`pip install` 安装超时或失败

使用国内镜像源重试：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3：`npm install` 安装超时或失败

使用国内镜像源重试：

```bash
npm install --registry https://registry.npmmirror.com
```

### Q4：后端启动报 `Connection refused` 或 `could not connect to server`

说明 PostgreSQL 未启动或连接配置有误，逐项检查：

1. **PostgreSQL 是否在运行？**
   - Windows：按 `Win + R`，输入 `services.msc`，查找 `postgresql-x64-16` 服务是否处于「正在运行」状态
   - Linux：`sudo systemctl status postgresql`

2. **`.env` 中的密码是否正确？** DATABASE_URL 里的密码必须与安装 PostgreSQL 时设置的密码一致

3. **数据库 `crypto_assistant` 是否已创建？** 用 `psql -U postgres` 连入后执行 `\l` 查看数据库列表

### Q5：后端启动报 Redis 连接错误

系统会输出 `Redis连接失败，系统将不使用缓存` 的警告，**不影响基本使用**。如果需要 Redis 功能：

1. 确认 Redis 服务已启动：
   - Memurai 用户：`memurai-cli ping` 应返回 `PONG`
   - 其他 Redis 安装：`redis-cli ping` 应返回 `PONG`
2. 如果 Redis 设了密码，需要在 `.env` 中配置 `REDIS_PASSWORD`

### Q6：前端页面空白或报 API 错误

1. 确认后端已经启动并且运行在 `8000` 端口
2. 前端 Vite 开发服务器会自动将 `/api/*` 请求代理到 `http://localhost:8000`，无需额外配置 Nginx

### Q7：`psql` 连接报 `peer authentication failed`（Linux）

修改 PostgreSQL 认证方式：

```bash
sudo nano /etc/postgresql/16/main/pg_hba.conf
```

找到：
```
local   all   postgres   peer
```

改为：
```
local   all   postgres   md5
```

保存后重启 PostgreSQL：

```bash
sudo systemctl restart postgresql
```

### Q8：端口被占用

如果提示端口被占用，查看并结束占用进程：

```bash
# Windows
netstat -aon | findstr :8000
taskkill /PID <进程ID> /F

# Linux
sudo lsof -i :8000
sudo kill -9 <进程PID>
```

---

# 端口速查表

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端开发服务器 (Vite) | 5173 | 开发时访问此端口 |
| 后端 API (Uvicorn) | 8000 | API 服务 + Swagger 文档 |
| PostgreSQL | 5432 | 数据库服务 |
| Redis | 6379 | 缓存服务 |
