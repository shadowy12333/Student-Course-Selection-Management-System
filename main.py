#uvicorn main:app --reload
# from database import SessionLocal, engine
# import models
# from security import get_password_hash

from fastapi import FastAPI
from database import engine, SessionLocal
import models
from security import get_password_hash
from routers import users, auth, courses


#确定主程序
app = FastAPI(title="校园选课管理系统 API", version="1.0.0")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(courses.router)
models.Base.metadata.create_all(bind=engine)

@app.on_event("startup")#当 FastAPI 应用被 Uvicorn 等 ASGI 服务器拉起后、但还没有开始接收外部请求之前，先运行这段代码。
def startup_event():
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.username=="admin").first()
        if not admin:
            hashed_pwd = get_password_hash("admin123")
            new_admin = models.User(
                username = "admin",
                hashed_password = hashed_pwd,
                role = "admin",
                is_active = True
            )
            db.add(new_admin)
            db.commit()
            print("管理员账号已经创建")
    finally:
        db.close()
@app.get("/")
def read_root():
    return {"message":"Welcome to the 学生选课系统"}


#遇到了问题，每次建库id自增，所以查找不到对应id，想办法让数据库自增






