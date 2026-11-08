from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
import crud, schemas
from security import verify_password, create_access_token

router = APIRouter(tags=["认证模块"])


@router.post("/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    # 用户名不存在和密码错误返回同一句提示，避免被用来探测哪些用户名已注册
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    # 业务规则：停用的账号不能登录
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被停用，无法登录")
    access_token = create_access_token(data={"sub": str(user.id)})
    # 角色由服务端返回，客户端不需要靠用户名去猜
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}
