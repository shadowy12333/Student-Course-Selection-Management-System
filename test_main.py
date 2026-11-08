# """自动化测试：在独立的测试库里跑完整个业务规则。
#
# 测试库地址优先读环境变量 TEST_DATABASE_URL；没设置时，用 .env 里的
# MySQL 账号拼出 test_agent_db 库（该库需要预先手动创建）。
# 密码不再硬编码在源码里，配置规则和 12-Factor 一致，见面试指南 7.10。
#
# 运行：pytest test_main.py -v
# """
#跑测试的时候用的，跑完后我自己又核查了一遍

import os
from urllib.parse import quote_plus

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from security import get_password_hash
import models

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _build_test_url():
    """外部可用 TEST_DATABASE_URL 覆盖，例如指向 SQLite 文件，做到零外部依赖。"""
    override = os.getenv("TEST_DATABASE_URL")
    if override:
        return override
    user = os.getenv("DB_USER", "root")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/test_agent_db"


engine = create_engine(_build_test_url(), pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 依赖覆盖：所有接口都用测试库，绝不碰开发库 agent_db
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ADMIN_USER = "admin"
ADMIN_PWD = "admin123"
STUDENT_PWD = "stu123456"


@pytest.fixture(autouse=True)
def fresh_db():
    # 每个用例都在全新的表上跑，用例之间互不污染
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(models.User(
        username=ADMIN_USER,
        hashed_password=get_password_hash(ADMIN_PWD),
        role="admin",
        is_active=True,
    ))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


# ------------------------------------------------------------------
#  小工具：让用例只表达业务意图，不重复拼请求
# ------------------------------------------------------------------

def login(username, password):
    return client.post("/login", data={"username": username, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def admin_headers():
    r = login(ADMIN_USER, ADMIN_PWD)
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


def make_student(username="stu1", password=STUDENT_PWD):
    r = client.post(
        "/users/",
        json={"username": username, "password": password, "role": "student"},
        headers=admin_headers(),
    )
    assert r.status_code == 200, r.text
    return r.json()


def student_headers(username="stu1", password=STUDENT_PWD):
    r = login(username, password)
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


def make_course(code="CS101", capacity=1, credits=3, name="测试课程", teacher="老师"):
    r = client.post(
        "/courses",
        json={"course_code": code, "course_name": name, "teacher": teacher,
              "credits": credits, "capacity": capacity},
        headers=admin_headers(),
    )
    assert r.status_code == 200, r.text
    return r.json()


def student_id(username="stu1"):
    users = client.get("/users/", headers=admin_headers()).json()
    return next(u["id"] for u in users if u["username"] == username)


# ------------------------------------------------------------------
#  认证与权限边界
# ------------------------------------------------------------------

def test_admin_login():
    r = login(ADMIN_USER, ADMIN_PWD)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_returns_real_role():
    assert login(ADMIN_USER, ADMIN_PWD).json()["role"] == "admin"
    make_student()
    assert login("stu1", STUDENT_PWD).json()["role"] == "student"


def test_login_error_message_is_uniform():
    """用户名不存在和密码错返回同一句话，避免被用来枚举已注册账号。"""
    a = login("no_such_user", "whatever123")
    b = login(ADMIN_USER, "wrong123456")
    assert a.status_code == b.status_code == 400
    assert a.json()["detail"] == b.json()["detail"] == "用户名或密码错误"


def test_auth_boundaries():
    assert client.get("/courses").status_code == 401                          # 未登录
    make_student()
    h = student_headers()
    assert client.get("/users/", headers=h).status_code == 403               # 学生调管理员接口
    assert client.post("/courses/1/enroll", headers=admin_headers()).status_code == 403  # 管理员不能选课


def test_change_password():
    make_student()
    h = student_headers()
    r = client.patch("/users/me/password",
                     json={"old_password": STUDENT_PWD, "new_password": "new123456"},
                     headers=h)
    assert r.status_code == 200
    assert login("stu1", STUDENT_PWD).status_code == 400
    assert login("stu1", "new123456").status_code == 200


# ------------------------------------------------------------------
#  选课业务规则
# ------------------------------------------------------------------

def test_student_enroll_and_full_capacity():
    course = make_course(capacity=1)
    make_student("stu1")
    make_student("stu2")
    assert client.post(f"/courses/{course['id']}/enroll", headers=student_headers("stu1")).status_code == 200
    r = client.post(f"/courses/{course['id']}/enroll", headers=student_headers("stu2"))
    assert r.status_code == 400 and "满员" in r.json()["detail"]


def test_duplicate_enroll_rejected():
    course = make_course(capacity=5)
    make_student()
    h = student_headers()
    assert client.post(f"/courses/{course['id']}/enroll", headers=h).status_code == 200
    assert client.post(f"/courses/{course['id']}/enroll", headers=h).status_code == 400


def test_closed_course_cannot_enroll():
    course = make_course(capacity=5)
    make_student()
    h = student_headers()
    assert client.patch(f"/courses/{course['id']}/status",
                        json={"status": "closed"}, headers=admin_headers()).status_code == 200
    r = client.post(f"/courses/{course['id']}/enroll", headers=h)
    assert r.status_code == 400 and "关闭" in r.json()["detail"]


def test_drop_course_restores_seat():
    course = make_course(capacity=1)
    make_student()
    h = student_headers()
    client.post(f"/courses/{course['id']}/enroll", headers=h)
    assert client.get(f"/courses/{course['id']}", headers=h).json()["remaining_seats"] == 0
    assert client.delete(f"/courses/{course['id']}/enroll", headers=h).status_code == 200
    assert client.get(f"/courses/{course['id']}", headers=h).json()["remaining_seats"] == 1


def test_disabled_account_cannot_login_and_old_token_rejected():
    course = make_course()
    make_student()
    h = student_headers()
    uid = student_id()
    assert client.patch(f"/users/{uid}/status",
                        json={"is_active": False}, headers=admin_headers()).status_code == 200
    assert login("stu1", STUDENT_PWD).status_code == 403
    assert client.get("/courses", headers=h).status_code == 403
    assert client.post(f"/courses/{course['id']}/enroll", headers=h).status_code == 403


def test_course_code_must_be_unique():
    make_course(code="DUP1")
    r = client.post("/courses",
                    json={"course_code": "DUP1", "course_name": "另一门", "teacher": "老师",
                          "credits": 2, "capacity": 5},
                    headers=admin_headers())
    assert r.status_code == 400 and "已存在" in r.json()["detail"]


def test_stats_and_enrollment_list():
    course = make_course(capacity=4)
    make_student()
    client.post(f"/courses/{course['id']}/enroll", headers=student_headers())
    st = client.get(f"/courses/{course['id']}/stats", headers=admin_headers()).json()
    assert st["enrolled_count"] == 1 and st["remaining_seats"] == 3
    names = [u["username"] for u in
             client.get(f"/courses/{course['id']}/students", headers=admin_headers()).json()]
    assert names == ["stu1"]


# ------------------------------------------------------------------
#  参数校验与删除保护
# ------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"course_code": "X1", "course_name": "课", "teacher": "师", "credits": 3, "capacity": 0},
    {"course_code": "X2", "course_name": "课", "teacher": "师", "credits": 3, "capacity": -1},
    {"course_code": "X3", "course_name": "课", "teacher": "师", "credits": -1, "capacity": 5},
    {"course_code": "", "course_name": "课", "teacher": "师", "credits": 3, "capacity": 5},
    {"course_code": "X5", "course_name": "", "teacher": "师", "credits": 3, "capacity": 5},
    {"course_code": "X6", "course_name": "课" * 21, "teacher": "师", "credits": 3, "capacity": 5},
], ids=["capacity=0", "capacity<0", "credits<0", "empty_code", "empty_name", "name_too_long"])
def test_invalid_course_params_return_422(payload):
    assert client.post("/courses", json=payload, headers=admin_headers()).status_code == 422


def test_role_escalation_rejected():
    r = client.post("/users/",
                    json={"username": "evil", "password": "pwd123456", "role": "admin"},
                    headers=admin_headers())
    assert r.status_code == 422
    r = client.post("/users/",
                    json={"username": "ok", "password": "pwd123456"},
                    headers=admin_headers())
    assert r.status_code == 200 and r.json()["role"] == "student"   # 不传 role 默认学生


def test_delete_admin_forbidden_and_cascade():
    # 每张全新表的第一条记录就是 admin，id 为 1
    assert client.get("/users/1", headers=admin_headers()).json()["role"] == "admin"
    assert client.delete("/users/1", headers=admin_headers()).status_code == 400
    assert client.delete("/users/9999", headers=admin_headers()).status_code == 404

    course = make_course(capacity=2)
    make_student()
    client.post(f"/courses/{course['id']}/enroll", headers=student_headers())
    r = client.delete(f"/users/{student_id()}", headers=admin_headers())
    assert r.status_code == 200 and r.json()["removed_enrollments"] == 1
    assert client.get(f"/courses/{course['id']}", headers=admin_headers()).json()["remaining_seats"] == 2


# ------------------------------------------------------------------
#  排序与分页
# ------------------------------------------------------------------

def test_sort_by_remaining_seats():
    many = make_course(code="A1", capacity=5, name="名额多")   # 剩 5
    few = make_course(code="B1", capacity=2, name="名额少")    # 选 1 人后剩 1
    mid = make_course(code="C1", capacity=3, name="名额中")    # 剩 3
    make_student()
    client.post(f"/courses/{few['id']}/enroll", headers=student_headers())
    r = client.get("/courses?sort_by=remaining&limit=100", headers=student_headers())
    assert r.status_code == 200
    items = r.json()
    ids = [c["id"] for c in items]
    assert ids.index(many["id"]) < ids.index(mid["id"]) < ids.index(few["id"])
    seats = {c["id"]: c["remaining_seats"] for c in items}
    assert seats[many["id"]] == 5 and seats[mid["id"]] == 3 and seats[few["id"]] == 1


def test_sort_by_credits_and_capacity():
    make_course(code="L1", credits=1, capacity=2)
    make_course(code="H1", credits=5, capacity=9)
    h = admin_headers()
    assert client.get("/courses?sort_by=credits", headers=h).json()[0]["course_code"] == "H1"
    assert client.get("/courses?sort_by=capacity", headers=h).json()[0]["course_code"] == "H1"


@pytest.mark.parametrize("qs", ["skip=-1", "limit=0", "limit=101"])
def test_pagination_params_validated(qs):
    assert client.get(f"/courses?{qs}", headers=admin_headers()).status_code == 422
    assert client.get("/courses?skip=0&limit=5", headers=admin_headers()).status_code == 200
