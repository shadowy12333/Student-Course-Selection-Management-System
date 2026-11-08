from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Literal

#pydantic
# class UserUpdate(BaseModel):
#     age:int
class UserCreate(BaseModel):
    username : str
    password: str = Field(...,min_length = 6 , max_length = 20)
    # 学生账号只能由管理员创建，且不允许通过请求体把自己提权成管理员
    role: Literal["student"] = "student"

class UserResponse(BaseModel):
    id : int
    username : str
    role : str
    is_active:bool
    model_config = ConfigDict(from_attributes = True)

class CourseCreate(BaseModel):
    # 在入口处就挡住空字符串/负数，避免脏数据写进数据库。
    # max_length 与 models.py 里 String(20) 的列宽保持一致，防止超长写入报错。
    course_code: str = Field(..., min_length=1, max_length=20)
    course_name: str = Field(..., min_length=1, max_length=20)
    teacher: str = Field(..., min_length=1, max_length=20)
    credits: int = Field(..., ge=0)   # 学分不能为负
    capacity: int = Field(..., gt=0)  # 容量必须大于 0，否则课程永远选不进去

class CourseResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    teacher: str
    credits: int
    capacity: int
    status: str
    # 只有课程列表接口会填充；其它接口返回 ORM 对象时该字段为 null
    remaining_seats: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
    role:str

class CourseStatusUpdate(BaseModel):
    status: str

class UserStatusUpdate(BaseModel):
    is_active: bool


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=20) # 新密码也限制一下长度


    #定义后续响应的模块，接口怎么收/发数据