from sqlalchemy.orm import Session
import models, schemas
from security import get_password_hash

def get_user(db:Session, user_id:int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db:Session, username:str):
    return db.query(models.User).filter(models.User.username == username).first()
def create_user(db:Session, user: schemas.UserCreate):
    hashed_pwd = get_password_hash(user.password)
    db_user = models.User(
        username = user.username,
        role = user.role,
        hashed_password = hashed_pwd,
        is_active = True
    )
    # db_user = models.User(name=user.name, email=user.email, age=user.age)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user
def delete_user(db: Session, user_id: int) -> int:
    # """删除学生账号，并先清掉他的选课记录。
    #
    # 顺序很重要：enrollments 表有指向 users 的外键，直接删用户会触发
    # IntegrityError（接口变成 500）。先删子记录再删父记录，名额也会自动释放。
    # 返回被清理的选课记录条数。
    # """
    user = get_user(db, user_id)
    if not user:
        return 0
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.student_id == user_id
    ).all()
    for enrollment in enrollments:
        db.delete(enrollment)
    db.delete(user)
    db.commit()
    return len(enrollments)




#增删改查

