from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, security

router = APIRouter()


# ============================================================
#  公共 · 课程浏览（学生和管理员登录后都能调用）
# ============================================================

@router.get("/courses", response_model=list[schemas.CourseResponse], tags=["学生", "管理员"])
def get_courses(
        keyword: str = "",
        sort_by: str = Query("id", description="排序：id / credits / capacity / remaining（按剩余名额从多到少）"),
        skip: int = Query(0, ge=0, description="跳过的条数"),
        limit: int = Query(10, ge=1, le=100, description="每页条数，最多 100"),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """课程列表：关键词搜索 + 排序（含剩余名额）+ 分页。

    按剩余名额排序在 SQL 层用关联子查询完成，先排序再分页，结果全局正确。
    """
    query = db.query(models.Course)

    # 1. 关键词搜索（如果传了关键词才搜）
    if keyword:
        query = query.filter(
            or_(
                models.Course.course_name.contains(keyword),
                models.Course.course_code.contains(keyword),
                models.Course.teacher.contains(keyword)
            )
        )

    # 2. 排序逻辑
    if sort_by == "credits":
        query = query.order_by(models.Course.credits.desc())   # 按学分降序
    elif sort_by == "capacity":
        query = query.order_by(models.Course.capacity.desc())  # 按容量降序
    elif sort_by in ("remaining", "remaining_seats"):
        # 关联子查询：对每门课算出已选人数，再用 容量 - 已选 得到剩余名额。
        # 放在 SQL 里而不是 Python 里，是为了保证 ORDER BY 在 LIMIT 之前生效。
        enrolled = (
            db.query(func.count(models.Enrollment.id))
            .filter(models.Enrollment.course_id == models.Course.id)
            .scalar_subquery()
        )
        query = query.order_by((models.Course.capacity - enrolled).desc(), models.Course.id.asc())
    else:
        query = query.order_by(models.Course.id.asc())         # 默认按 ID 升序
    query = query.offset(skip).limit(limit)
    courses = query.all()

    # 3. 顺带给出每门课的剩余名额：一次 group by 批量统计，避免 N+1 查询
    if courses:
        counts = dict(
            db.query(models.Enrollment.course_id, func.count(models.Enrollment.id))
            .filter(models.Enrollment.course_id.in_([c.id for c in courses]))
            .group_by(models.Enrollment.course_id)
            .all()
        )
        for course in courses:
            course.remaining_seats = course.capacity - counts.get(course.id, 0)
    return courses


@router.get("/courses/{course_id}", tags=["学生", "管理员"])
def get_course_detail(
        course_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    # 统计当前选课人数
    enrolled_count = db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).count()
    remaining = course.capacity - enrolled_count

    # 如果名额满了，直接返回 0，防止出现负数
    if remaining < 0:
        remaining = 0

    return {
        "id": course.id,
        "course_code": course.course_code,
        "course_name": course.course_name,
        "teacher": course.teacher,
        "credits": course.credits,
        "capacity": course.capacity,
        "status": course.status,
        "enrolled_count": enrolled_count,
        "remaining_seats": remaining  # 剩余名额
    }


# ============================================================
#  管理员 · 课程管理（只有 admin 账号能调用）
# ============================================================

@router.post("/courses", response_model=schemas.CourseResponse, tags=["管理员"])
def create_course(
        course: schemas.CourseCreate,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    existing_course = db.query(models.Course).filter(models.Course.course_code == course.course_code).first()
    if existing_course:
        raise HTTPException(status_code=400, detail="课程编号已存在")
    new_course = models.Course(
        course_code=course.course_code,
        course_name=course.course_name,
        teacher=course.teacher,
        credits=course.credits,
        capacity=course.capacity
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    return new_course


@router.get("/courses/{course_id}/students", response_model=list[schemas.UserResponse], tags=["管理员"])
def get_course_students(
        course_id: int,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    enrollment = db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).all()
    return [enroll.student for enroll in enrollment]


@router.get("/courses/{course_id}/stats", tags=["管理员"])
def get_course_stats(
        course_id: int,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    # 计算数据
    enrolled_count = db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).count()
    remaining = max(0, course.capacity - enrolled_count)  # 防负数

    # 计算百分比（保留两位小数）
    fill_rate = f"{(enrolled_count / course.capacity * 100):.2f}%" if course.capacity > 0 else "0%"

    return {
        "course_id": course.id,
        "course_name": course.course_name,
        "capacity": course.capacity,
        "enrolled_count": enrolled_count,
        "remaining_seats": remaining,
        "fill_rate": fill_rate  # 满员率
    }


@router.patch("/courses/{course_id}/status", response_model=schemas.CourseResponse, tags=["管理员"])
def update_course_status(
        course_id: int,
        status_update: schemas.CourseStatusUpdate,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    if status_update.status not in ["open", "closed"]:
        raise HTTPException(status_code=400, detail="状态只能是 open 或 closed")

    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    course.status = status_update.status
    db.commit()
    db.refresh(course)
    return course


@router.put("/courses/{course_id}", response_model=schemas.CourseResponse, tags=["管理员"])
def update_course(
        course_id: int,
        course_update: schemas.CourseCreate,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if course_update.course_code != course.course_code:
        exist = db.query(models.Course).filter(models.Course.course_code == course_update.course_code).first()
        if exist:
            raise HTTPException(status_code=400, detail="新课程编号已被占用")
    course.course_code = course_update.course_code
    course.course_name = course_update.course_name
    course.teacher = course_update.teacher
    course.credits = course_update.credits
    course.capacity = course_update.capacity
    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}", tags=["管理员"])
def delete_course(
        course_id: int,
        db: Session = Depends(get_db),
        current_admin: models.User = Depends(security.get_current_admin)
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    enrollment_count = db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).count()
    if enrollment_count > 0:
        raise HTTPException(status_code=400, detail=f"该课程已有 {enrollment_count} 名学生选课，无法删除。请先处理学生的选课记录。")
    db.delete(course)
    db.commit()
    return {"message": "课程删除成功"}


# ============================================================
#  学生 · 选课（只有 student 账号能调用）
# ============================================================

@router.get("/me/courses", response_model=list[schemas.CourseResponse], tags=["学生"])
def get_my_courses(
        db: Session = Depends(get_db),
        current_student: models.User = Depends(security.get_current_student)
):
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.student_id == current_student.id
    ).all()
    return [e.course for e in enrollments]


@router.post("/courses/{course_id}/enroll", tags=["学生"])
def enroll_course(
        course_id: int,
        db: Session = Depends(get_db),
        current_student: models.User = Depends(security.get_current_student)  # 动态获取当前登录用户
):
    student_id = current_student.id  # 拿到真实的 ID

    # 1. 检查课程是否存在
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    # 2. 检查状态
    if course.status != "open":
        raise HTTPException(status_code=400, detail="该课程已关闭选课")

    # 3. 检查是否已经选过
    existing_enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.student_id == student_id,
        models.Enrollment.course_id == course_id
    ).first()
    if existing_enrollment:
        raise HTTPException(status_code=400, detail="你已经选过这门课了")

    # 4. 检查容量
    current_enrolled_count = db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).count()
    if current_enrolled_count >= course.capacity:
        raise HTTPException(status_code=400, detail="选课失败：该课程已经满员。")

    # 5. 写入
    new_enrollment = models.Enrollment(student_id=student_id, course_id=course_id)
    db.add(new_enrollment)
    db.commit()

    return {"message": "选课成功！"}


@router.delete("/courses/{course_id}/enroll", tags=["学生"])
def drop_course(
        course_id: int,
        db: Session = Depends(get_db),
        current_student: models.User = Depends(security.get_current_student)
):
    enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.student_id == current_student.id,
        models.Enrollment.course_id == course_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="你并没有选择这门课，无法退选")

    db.delete(enrollment)
    db.commit()
    return {"message": "退选成功，名额已恢复"}
