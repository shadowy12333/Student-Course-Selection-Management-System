import os
from datetime import datetime,timedelta,timezone
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models
from jose import jwt, JWTError
from dotenv import load_dotenv
load_dotenv()
#CryptContext：passlib 的核心类，统一管理密码哈希算法，提供 hash() 和 verify() 两个方法。
#schemes=["bcrypt"]：指定使用 bcrypt 算法。bcrypt 会自动加盐、每次哈希结果不同，防彩虹表攻击
# deprecated="auto"：自动标记非首选算法为"过时"。
pwd_context = CryptContext(schemes=["bcrypt"],deprecated = "auto")

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
#密钥全部由环境变量注入，没有硬编码在源码中。

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def get_password_hash(password:str):
    return pwd_context.hash(password)

def verify_password(plain_password:str,hashed_password:str):
    return pwd_context.verify(plain_password,hashed_password)

def create_access_token(data:dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})
    encode_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
    return encode_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail = "无效身份",headers = {"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms= [ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    # 停用账号的旧 Token 立刻失效，避免停用后仍可浏览课程等接口
    if not user.is_active:
        raise HTTPException(status_code = 403, detail="账号已被停用")
    return user

#权限区分
def get_current_admin(current_user:models.User = Depends(get_current_user)):
    if current_user.role !="admin":
        raise HTTPException(status_code=403,detail = "权限不足，无法操作")
    if not current_user.is_active:
        raise HTTPException(status_code = 403,detail="账号被停用")
    return current_user

def get_current_student(current_user:models.User = Depends(get_current_user)):
    if current_user.role !="student":
        raise HTTPException(status_code = 403, detail = "需要学生身份")
    if not current_user.is_active:
        raise HTTPException(status_code = 403,detail = "账号被停用")
    return current_user


#权限区分，哈希密码，验证和解析 token