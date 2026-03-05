# 🚄 火车票订票系统

一个基于 FastAPI 后端和 Streamlit 前端的火车票订票系统。

## 功能特点

### 用户功能
- 🔐 用户注册/登录（JWT 认证）
- 🔍 车票查询（按出发地、目的地、日期）
- 💺 座位选择（多种座位类型）
- 📋 订单管理（创建、支付、取消、退票）
- 👤 个人信息管理

### 座位类型
- 硬座 / 硬卧
- 软座 / 软卧
- 一等座 / 二等座 / 商务座

### 订单状态
- 待支付 → 已支付 → 已使用
- 待支付 → 已取消
- 已支付 → 已退票

## 项目结构

```
train-booking-system/
├── backend/
│   ├── main.py           # FastAPI 应用入口
│   ├── database.py       # 数据库配置
│   ├── models.py         # SQLAlchemy 模型
│   ├── schemas.py        # Pydantic 模式
│   ├── config.py         # 配置文件
│   ├── utils.py          # 工具函数
│   └── routers/
│       ├── auth.py       # 认证路由
│       ├── trains.py     # 车次管理路由
│       ├── orders.py     # 订单管理路由
│       └── payment.py    # 支付路由
├── frontend/
│   ├── app.py            # Streamlit 主应用
│   ├── config.py         # 前端配置
│   ├── utils.py          # 前端工具函数
│   └── pages/
│       ├── _01_登录注册.py
│       ├── _02_车票查询.py
│       ├── _03_座位选择.py
│       ├── _04_订单确认.py
│       └── _05_我的订单.py
├── requirements.txt      # Python 依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd backend
python main.py
```

后端服务将在 http://localhost:8000 启动
API 文档：http://localhost:8000/docs

### 3. 启动前端应用

打开新终端：

```bash
cd frontend
streamlit run app.py
```

前端应用将在 http://localhost:8501 启动

## 默认测试账号

系统启动时会自动创建测试数据：

- **用户名**: testuser
- **密码**: 123456

## API 端点

### 认证
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息

### 车次
- `GET /api/trains/search` - 查询车次
- `GET /api/trains/{id}/seats` - 获取座位
- `POST /api/trains/{id}/seats/check` - 检查座位可用性
- `GET /api/trains` - 获取所有车次

### 订单
- `POST /api/orders` - 创建订单
- `GET /api/orders` - 获取用户订单
- `GET /api/orders/{id}` - 获取订单详情
- `PUT /api/orders/{id}/cancel` - 取消订单
- `POST /api/orders/{id}/refund` - 退票

### 支付
- `POST /api/payment` - 处理支付
- `POST /api/payment/{order_id}/simulate` - 模拟支付

## 技术栈

### 后端
- **FastAPI** - 现代高性能 Web 框架
- **SQLAlchemy** - ORM 框架
- **SQLite** - 数据库（可替换为 PostgreSQL/MySQL）
- **JWT** - 用户认证
- **Passlib** - 密码加密

### 前端
- **Streamlit** - Python Web 应用框架
- **Requests** - HTTP 客户端

## 配置

复制环境变量配置文件：

```bash
cp backend/.env.example backend/.env
```

修改 `backend/.env` 中的配置项。

## 注意事项

1. 这是一个演示系统，支付功能为模拟实现
2. 生产环境需要：
   - 修改 JWT SECRET_KEY
   - 使用生产级数据库（PostgreSQL/MySQL）
   - 配置 HTTPS
   - 集成真实支付网关
   - 添加日志和监控

## 开发计划

- [ ] 管理员后台
- [ ] 车次管理界面
- [ ] 座位图可视化
- [ ] 邮件/短信通知
- [ ] 候补购票功能
- [ ] 多语言支持

## License

MIT License
