from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, crud, schemas
import security

router = APIRouter(prefix="/users")


# ============================================================
#  管理员 · 用户管理（只有 admin 账号能调用）
# ============================================================

@router.get("/", response_model=list[schemas.UserResponse], tags=["管理员"])
def get_students(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(security.get_current_admin)
):
    # 只查 role 为 student 的用户
    return db.query(models.User).filter(models.User.role == "student").all()


@router.post("/", response_model=schemas.UserResponse, tags=["管理员"])
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(security.get_current_admin)
):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="该用户名已被注册")
    # 双保险：不论请求体传什么角色，创建出来的一律是学生账号
    return crud.create_user(db=db, user=user.model_copy(update={"role": "student"}))


@router.get("/{user_id}", response_model=schemas.UserResponse, tags=["管理员"])
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(security.get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.patch("/{user_id}/status", response_model=schemas.UserResponse, tags=["管理员"])
def toggle_user_status(
    user_id: int,
    status_update: schemas.UserStatusUpdate,   # 从 Body 接收
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(security.get_current_admin)   # 管理员权限校验
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能停用管理员账号")   # 防呆设计

    user.is_active = status_update.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", tags=["管理员"])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(security.get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的账号")
    # 复用 crud 里的删除逻辑：先清选课记录再删用户，避免外键报错
    removed = crud.delete_user(db=db, user_id=user_id)
    return {"message": "用户删除成功", "removed_enrollments": removed}


# ============================================================
#  学生（只有 student 账号能调用）
# ============================================================

@router.patch("/me/password", tags=["学生"])
def change_password(
        pwd_update: schemas.PasswordUpdate,
        db: Session = Depends(get_db),
        current_student: models.User = Depends(security.get_current_student)
):
    if not security.verify_password(pwd_update.old_password, current_student.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")

    current_student.hashed_password = security.get_password_hash(pwd_update.new_password)
    db.commit()
    return {"message": "密码修改成功，请重新登录"}
