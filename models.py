from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

#------------------定义ORM------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer,primary_key=True,index = True)
    username = Column(String(20),unique = True,  index = True,nullable = False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20),default = "student")
    # 账号是否启用（停用后不能登录）
    is_active = Column(Boolean, default = True)

    enrollments = relationship("Enrollment",back_populates="student")
    #  2. 课程表
class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer,primary_key = True,index = True)
    course_code = Column(String(20),index = True,nullable = False,unique = True)#课程编号，不能重复
    course_name = Column(String(20),nullable = False)
    teacher = Column(String(20),nullable = False)
    credits = Column(Integer,default = 0)#学分
    capacity = Column(Integer,nullable = False)
    status = Column(String(20),default = "open")
    enrollments = relationship("Enrollment",back_populates="course")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer,primary_key = True,index = True)
    student_id = Column(Integer,ForeignKey("users.id"),nullable = False)
    course_id = Column(Integer,ForeignKey("courses.id"),nullable = False)

    __table_args__ = (UniqueConstraint("student_id","course_id",name="_student_course_unique"),)
    student = relationship("User",back_populates="enrollments")
    course = relationship("Course",back_populates="enrollments")


#定义数据库怎么存数据



