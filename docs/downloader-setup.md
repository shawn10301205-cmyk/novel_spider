# 小说下载功能部署指南

## 架构概览

```
novel_spider (:8081)             Tomato-Novel-Downloader (:18423)
├── 排行榜 / 数据分析              ├── 解密引擎（内置）
├── Web 看板                      ├── 下载管理
├── 飞书推送              ──调用──→ ├── Web API
└── 下载接口（代理转发）            └── 书库管理
```

novel_spider 通过 HTTP 调用 Tomato-Novel-Downloader 的 Web API 实现小说下载。
Tomato 负责解密和下载正文，novel_spider 负责转发请求和展示进度。

---

## 1. 安装 Tomato-Novel-Downloader

### 下载

从 [GitHub Releases](https://github.com/zhongbai2333/Tomato-Novel-Downloader/releases) 下载对应平台的可执行文件：

| 平台 | 文件名 |
|------|--------|
| macOS (M1/M2) | `TomatoNovelDownloader-macOS_arm64-vX.X.X` |
| Windows | `TomatoNovelDownloader-Win64-vX.X.X.exe` |
| Linux x86 | `TomatoNovelDownloader-Linux_amd64-vX.X.X` |
| Linux ARM | `TomatoNovelDownloader-Linux_arm64-vX.X.X` |

### 安装

```bash
# macOS / Linux
chmod +x TomatoNovelDownloader-macOS_arm64-vX.X.X
mv TomatoNovelDownloader-macOS_arm64-vX.X.X /usr/local/bin/tomato-dl

# 或放到项目目录
mv TomatoNovelDownloader-macOS_arm64-vX.X.X ./tomato-dl
chmod +x ./tomato-dl
```

### 启动服务

```bash
# 启动 Web 服务（默认端口 18423）
./tomato-dl --server

# 带密码保护
./tomato-dl --server --password your_password

# 指定数据目录
./tomato-dl --server --data-dir /path/to/data
```

启动后访问 `http://127.0.0.1:18423/` 可打开 Web 管理界面。

---

## 2. 配置 novel_spider

在 `config.yaml` 或 `config.local.yaml` 中配置 Tomato 服务地址：

```yaml
download:
  tomato_url: 'http://127.0.0.1:18423'
  request_timeout: 15
```

如果 Tomato 运行在其他机器上，修改 `tomato_url` 为对应地址。

---

## 3. 使用方式

### 命令行

```bash
# 检查 Tomato 服务连接
python3 main.py download --check

# 查看书籍信息
python3 main.py download 7143038691944959011 --info-only

# 查看章节列表
python3 main.py download 7143038691944959011 --chapters-only

# 提交下载任务
python3 main.py download 7143038691944959011

# 查看所有下载任务状态
python3 main.py download --status
```

### Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tomato/check` | GET | 检查 Tomato 服务状态 |
| `/api/book/info?book_id=xxx` | GET | 书籍详情 |
| `/api/book/search?q=关键词` | GET | 搜索小说 |
| `/api/book/chapters?book_id=xxx` | GET | 章节目录 |
| `/api/book/download` | POST | 提交下载任务 (`{"book_id":"xxx"}`) |
| `/api/book/download/status` | GET | 所有任务进度 |
| `/api/book/download/cancel` | POST | 取消任务 (`{"job_id":1}`) |
| `/api/book/library` | GET | 已下载书库 |

### API 调用示例

```bash
# 检查服务
curl http://localhost:8081/api/tomato/check

# 查看书籍信息
curl "http://localhost:8081/api/book/info?book_id=7143038691944959011"

# 搜索
curl "http://localhost:8081/api/book/search?q=十日终焉"

# 提交下载
curl -X POST http://localhost:8081/api/book/download \
  -H "Content-Type: application/json" \
  -d '{"book_id":"7143038691944959011"}'

# 查看进度
curl http://localhost:8081/api/book/download/status
```

---

## 4. 同时启动两个服务

### 手动启动

```bash
# 终端1：启动 Tomato
./tomato-dl --server

# 终端2：启动 novel_spider
python3 server.py
```

### 后台运行（推荐）

```bash
# Tomato 后台运行
nohup ./tomato-dl --server > tomato.log 2>&1 &

# novel_spider 后台运行
nohup python3 server.py > spider.log 2>&1 &
```

### 使用 systemd（Linux 服务器）

```ini
# /etc/systemd/system/tomato-dl.service
[Unit]
Description=Tomato Novel Downloader
After=network.target

[Service]
ExecStart=/path/to/tomato-dl --server
WorkingDirectory=/path/to/data
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 5. 注意事项

- Tomato 服务必须先于 novel_spider 启动
- 下载的文件保存在 Tomato 的工作目录中
- 如果 Tomato 未启动，书籍信息查看仍可使用（回退到直接爬网页）
- 下载功能则必须依赖 Tomato 服务
