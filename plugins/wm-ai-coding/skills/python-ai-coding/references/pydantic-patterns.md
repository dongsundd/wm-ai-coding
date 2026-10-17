# Pydantic 验证模式

本文件为 OpenSpec `languages-python/spec.md` 中规则 10（外部输入必须验证）提供**可复用代码模板**。

---

## 1. 基础 Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# ✅ 定义输入 schema
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., regex=r"^[\w.]+@[\w.]+$")
    age: int = Field(..., ge=0, le=150)
    is_active: bool = True
    created_at: Optional[datetime] = None

# 使用
def create_user(data: UserCreate) -> User:
    # data 已经被验证，可直接使用
    return User.objects.create(**data.model_dump())
```

## 2. 字段约束

```python
from pydantic import BaseModel, Field, conint, constr

class ProductCreate(BaseModel):
    # 字符串约束
    name: constr(min_length=1, max_length=200)
    sku: constr(regex=r"^[A-Z]{3}-\d{6}$")  # ABC-123456

    # 数值约束
    price: conint(ge=0, le=1_000_000)  # 0-100万
    stock: conint(ge=0)

    # 列表约束
    tags: list[constr(min_length=1, max_length=20)] = Field(
        default_factory=list,
        max_items=10
    )
```

## 3. 自定义验证器

```python
from pydantic import BaseModel, validator

class UserCreate(BaseModel):
    name: str
    password: str
    password_confirm: str

    @validator("name")
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @validator("password_confirm")
    def passwords_match(cls, v: str, values: dict) -> str:
        if "password" in values and v != values["password"]:
            raise ValueError("passwords do not match")
        return v
```

## 4. 嵌套模型

```python
class Address(BaseModel):
    city: str
    street: str
    zip_code: str = Field(..., regex=r"^\d{5}$")

class UserCreate(BaseModel):
    name: str
    age: int
    address: Address  # 嵌套模型，自动验证

# 使用
data = UserCreate(
    name="Alice",
    age=30,
    address={"city": "Beijing", "street": "Main St", "zip_code": "10000"}
)
```

## 5. FastAPI 集成

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

@app.post("/users")
def create_user(data: UserCreate) -> dict:
    # FastAPI 自动验证请求体，失败时返回 422
    # 此处 data 已被验证
    user = User.objects.create(**data.model_dump())
    return {"id": user.id}
```

## 6. SQLAlchemy 集成（ORM 模式）

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserSchema(BaseModel):
    """Pydantic schema for User ORM model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    age: int

# 从 ORM 对象转换
user_orm = User.objects.get(id=1)
user_dto = UserSchema.model_validate(user_orm)  # 自动从 ORM 属性填充

# 反向：从 DTO 创建 ORM 对象
user_new = User(**user_dto.model_dump())
```

## 7. 错误处理

```python
from pydantic import ValidationError
from fastapi import HTTPException

def process_request(raw_data: dict) -> UserCreate:
    try:
        return UserCreate(**raw_data)
    except ValidationError as e:
        # 转换为 422 Unprocessable Entity
        raise HTTPException(
            status_code=422,
            detail=e.errors()
        )
```

## 8. 配置（pydantic-settings）

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件加载"""

    # 必填
    database_url: str
    api_key: str

    # 可选 with default
    log_level: str = "INFO"
    max_retries: int = Field(default=3, ge=1, le=10)
    cache_ttl: int = Field(default=300, ge=0)  # 秒

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 使用
settings = Settings()
# 自动从环境变量或 .env 读取
# DATABASE_URL=postgres://... python app.py
```

## 9. 业务规则验证

```python
from pydantic import BaseModel, root_validator
from typing import Optional

class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float

    @root_validator
    def check_transfer(cls, values: dict) -> dict:
        if values.get("from_account") == values.get("to_account"):
            raise ValueError("from_account and to_account must differ")
        if values.get("amount", 0) <= 0:
            raise ValueError("amount must be positive")
        return values
```

## 10. 完整 FastAPI + Pydantic + SQLAlchemy 模式

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Generator

app = FastAPI()

# 1. Pydantic schema（输入/输出边界）
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., regex=r"^[\w.]+@[\w.]+$")
    age: int = Field(..., ge=0, le=150)

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    email: str
    age: int

# 2. DB session 依赖注入
def get_db() -> Generator[Session, None, None]:
    db = Session()
    try:
        yield db
    finally:
        db.close()

# 3. Endpoint with auto-validation
@app.post("/users", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    user = User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserResponse:
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user
```
