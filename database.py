import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# ------------------------------------------------------------
# 存储后端：通过 .env 的 STORAGE_TYPE 切换，API 与命令行客户端无需改动
#   mysql          -> MySQL 数据库（需先手动创建对应的库）
#   sqlite / local -> 本地文件 data/local.db（标准允许的基础版本地持久化方案）
# 两种模式共用同一套 SQLAlchemy ORM 模型与数据库唯一约束。
# ------------------------------------------------------------
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "mysql").strip().lower()

if STORAGE_TYPE in ("sqlite", "local"):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    # 可用 SQLITE_DB_PATH 自定义本地库位置（不填则为 data/local.db）
    DB_FILE = os.getenv("SQLITE_DB_PATH") or os.path.join(DATA_DIR, "local.db")
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    DB_FILE = DB_FILE.replace(os.sep, "/")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
        # SQLite 默认不开启外键约束，打开后与 MySQL 行为保持一致
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
elif STORAGE_TYPE == "mysql":
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    raise ValueError(
        f"未知的 STORAGE_TYPE={STORAGE_TYPE!r}，只支持 mysql / sqlite（local）"
    )

# 隐藏 MySQL 连接串里的账号密码后再打印，方便启动时确认当前用的是哪个后端
print(f"[storage] 当前后端={STORAGE_TYPE} | {SQLALCHEMY_DATABASE_URL.split('@')[-1]}")

SessionLocal = sessionmaker(autocommit=False,autoflush=False,bind = engine)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db#生成器 不会一次性把所有数据放进内存，适合处理大文件、大列表、流式数据
    finally:
        db.close()