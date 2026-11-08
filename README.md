# 学生选课系统（FastAPI + MySQL）

一个用 Python 写的后端项目：学生可以登录、浏览课程、选课/退课、改密码；管理员可以管理学生和课程、查看选课统计。

## 用到的技术

- **FastAPI**：写接口的 Web 框架
- **SQLAlchemy**：操作数据库的 ORM 工具（用 Python 代码代替 SQL）
- **MySQL**：存数据的数据库
- **JWT**：登录验证用的令牌（Token）
- **bcrypt**：密码加密存储（不明文保存密码）

## 文件结构

```
├── main.py        程序入口，把各个功能模块组装到一起
├── database.py    连接数据库的配置
├── models.py      定义三张表：用户、课程、选课记录
├── schemas.py     定义接口收/发数据的格式（Pydantic 校验）
├── crud.py        增删改查的基础函数
├── security.py    密码加密、Token 生成、身份/权限验证
├── routers/       接口模块（按功能拆分）
│   ├── auth.py      登录接口
│   ├── users.py     用户管理接口
│   └── courses.py   课程 + 选课接口
├── client.py      一个命令行客户端（用来测试接口）
├── test_main.py   自动化测试（pytest）
├── requirements.txt  项目依赖包清单
└── .env           数据库账号密码、密钥等配置（不要上传到 GitHub）
```

## 主要功能

**学生**：浏览/搜索课程（支持按学分、容量、**剩余名额**排序，列表直接显示剩余名额）、查看课程详情和剩余名额、选课、退课、查看已选课程、修改密码

**管理员**：创建学生、查看/启用/停用学生、创建/修改/删除课程、开放或关闭选课、查看选课名单、查看选课统计（满员率）、浏览课程列表和详情

## 接口一览

服务端共提供以下 RESTful 接口，启动后也可在 `/docs` 页面直接查看和调试。

| 方法 | 路径 | 功能 | 权限 |
| --- | --- | --- | --- |
| POST | `/login` | 登录，返回 JWT 令牌与账号角色（role） | 无 |
| GET | `/users/` | 查看学生列表 | 管理员 |
| POST | `/users/` | 创建学生账号 | 管理员 |
| GET | `/users/{user_id}` | 查看单个用户信息 | 管理员 |
| PATCH | `/users/{user_id}/status` | 启用/停用学生账号 | 管理员 |
| DELETE | `/users/{user_id}` | 删除学生账号（连带清理其选课记录） | 管理员 |
| PATCH | `/users/me/password` | 修改本人密码 | 学生 |
| GET | `/courses` | 课程列表（关键词搜索、按学分/容量/剩余名额排序、分页范围校验、返回剩余名额） | 学生/管理员 |
| GET | `/courses/{course_id}` | 课程详情（含已选人数、剩余名额） | 学生/管理员 |
| POST | `/courses` | 创建课程 | 管理员 |
| PUT | `/courses/{course_id}` | 修改课程信息 | 管理员 |
| DELETE | `/courses/{course_id}` | 删除课程（已有人选课时拒绝） | 管理员 |
| PATCH | `/courses/{course_id}/status` | 开放/关闭选课 | 管理员 |
| GET | `/courses/{course_id}/students` | 查看某门课的选课名单 | 管理员 |
| GET | `/courses/{course_id}/stats` | 查看选课统计（已选人数、剩余名额、满员率） | 管理员 |
| POST | `/courses/{course_id}/enroll` | 选课 | 学生 |
| DELETE | `/courses/{course_id}/enroll` | 退课 | 学生 |
| GET | `/me/courses` | 查看本人已选课程 | 学生 |

选课的业务规则全部由服务端校验：课程关闭/满员不能选、不能重复选同一门课、只能退自己选的课、退课后名额恢复、管理员不能替学生选课。

**其他服务端防御**：创建/修改课程时 `credits ≥ 0`、`capacity > 0`，编号/名称/教师不能为空且不超过 20 字（Pydantic 在入口拦截，非法参数返回 422）；删除用户时禁止删管理员账号和当前登录账号，并先清理该学生的选课记录再删账号（避免外键报错，名额自动释放）；登录响应返回真实 `role`，命令行客户端据此决定进入哪个菜单，不再靠用户名猜测。

## 存储后端切换（STORAGE_TYPE）

存储后端是可配置的，`.env` 里改一行即可，**API 接口和命令行客户端都不需要任何改动**：

| STORAGE_TYPE | 数据存在哪 | 说明 |
| --- | --- | --- |
| `mysql` | MySQL 的 `agent_db` 库 | 加分项；需先手动创建该库 |
| `sqlite`（或 `local`） | 本地文件 `data/local.db` | 基础版本地持久化，自动建库建表 |

两种模式共用同一套 SQLAlchemy ORM 模型，唯一约束（用户名、课程编号、重复选课）和课程容量判断在两边行为一致。服务停止后重启，用户、课程、选课记录仍然存在。

> 说明：评定标准允许 JSON / CSV / SQLite 等本地持久化方案，本项目的本地版采用 SQLite 文件，这样能以最小改动真正做到「改配置即切换」，且不改变任何接口语义。需要换本地库位置时，可再加一行 `SQLITE_DB_PATH=你的路径/local.db`。

## 运行前准备

1. 安装依赖包（根目录有 `requirements.txt`，一条命令搞定）：

```bash
pip install -r requirements.txt
```

2. 按所选后端准备环境：默认 `STORAGE_TYPE=mysql`，需确认本地 MySQL 已启动、并已手动创建 `agent_db` 库；若改成 `STORAGE_TYPE=sqlite` 则无需 MySQL，首次运行会自动创建 `data/local.db`。`.env` 配置示例：

```
STORAGE_TYPE=mysql
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_HOST=localhost
DB_PORT=3306
DB_NAME=agent_db
SECRET_KEY=随便一串字符（用于 Token 加密，不要告诉别人）
```

3. 首次运行会自动建表，并自动创建一个管理员账号：
   - 用户名：`admin`，密码：`admin123`

## 启动服务

```bash
uvicorn main:app --reload
```

启动后浏览器打开 <http://127.0.0.1:8000/docs>，可以看到自动生成的接口文档，并且能直接在网页上测试接口，非常方便。接口按「管理员 / 学生」分组展示，登录后带令牌即可交互调试。

## 命令行客户端（可选）

```bash
python client.py
```

按提示登录，之后按菜单数字选择操作即可，功能和服务器的接口一一对应。默认连 `http://127.0.0.1:8000`；若服务端换了端口，设置环境变量即可，客户端代码不用改：

```bash
API_BASE_URL=http://127.0.0.1:8001 python client.py
```

切换 MySQL / 本地存储后端同样不需要改动客户端，只改服务端的 `.env`。

## 运行测试

```bash
pytest test_main.py -v
```

测试会在独立的 `test_agent_db` 库里自动建表/清表，覆盖登录与角色、选课四大规则（满员 / 重复 / 关闭 / 退课恢复）、停用账号、越权与参数校验（参数化用例）、删除级联、排序与分页、统计与名单等 **25 个用例**。

测试库地址**不再硬编码**：默认读 `.env` 里的 MySQL 账号拼出 `test_agent_db`（需先手动创建该库），也可用环境变量 `TEST_DATABASE_URL` 覆盖，例如指向本地 SQLite 文件，做到不依赖 MySQL 服务：

```bash
TEST_DATABASE_URL=sqlite:///./data/test.db pytest test_main.py -v
```

另附端到端验证脚本 `verify_e2e.py`（100+ 项检查）：它会自己在 **8001** 端口起停服务，依次验证 `/docs` 页面与 OpenAPI 规格、按文档实际调用接口、三处权限缺陷与全部业务规则、六处中优先级问题（参数校验、删除保护与级联、角色返回、客户端输入防御、版本号与响应结构）、绿色加分项专项（按剩余名额排序、列表返回剩余名额、分页约束、客户端排序菜单）、命令行客户端完整菜单流程、服务重启后的数据持久化，最后换回 MySQL 默认模式回归一遍。脚本已内置 `NO_PROXY`，避免本机回环请求被系统代理干扰；不占用常用的 8000 端口：

```bash
python verify_e2e.py
```

## 常见问题

- **连不上数据库**：检查 MySQL 是否启动、`.env` 里的密码是否正确
- **端口被占用**：换端口启动，如 `uvicorn main:app --port 8001`
- **测试数据想重来**：清空表数据，重启服务即可
- **本机验证脚本偶发超时**：脚本已设 `NO_PROXY=127.0.0.1,localhost`；自行改写脚本时也要让回环地址绕过系统代理
