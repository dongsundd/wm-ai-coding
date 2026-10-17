# Python 错误处理模式

本文件为 OpenSpec `languages-python/spec.md` 中规则 3、6、9（异常类型 / 禁止 except:pass / DB session 生命周期）提供**可复用代码模板**。

---

## 1. 异常类型层级

```
BaseException
├── SystemExit / KeyboardInterrupt / GeneratorExit   # 永远不要捕获
└── Exception
    ├── StopIteration
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   └── OverflowError
    ├── AttributeError
    ├── ImportError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── NameError
    ├── OSError
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   └── ConnectionError
    ├── RuntimeError
    ├── TypeError
    └── ValueError
```

**黄金法则**：永远不要捕获 `Exception` 以上层级。`SystemExit`、`KeyboardInterrupt` 是用户主动中断，吞掉会导致 Ctrl+C 无效。

## 2. 具体异常类型

```python
import json
from pathlib import Path
from typing import Optional

# ❌ Wrong: 不知道哪里出错
def read_config(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}  # 隐藏所有错误

# ✅ Correct: 精确捕获
def read_config(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        logger.warning("config file not found: %s, using defaults", path)
        return default_config()
    except json.JSONDecodeError as e:
        logger.error("invalid JSON in %s at line %d", path, e.lineno)
        raise ConfigError(f"invalid config: {e}") from e
    except PermissionError:
        logger.error("no permission to read %s", path)
        raise
```

## 3. 禁止 silent except（规则 6）

```python
# ❌ Wrong: silent swallow
try:
    value = parse(input)
except:
    pass

# ❌ Wrong: catch-all without action
try:
    risky_op()
except Exception:
    pass

# ✅ Correct: log + handle
try:
    value = parse(input)
except ValueError as e:
    logger.warning("parse failed: %s, using default", e)
    value = default_value

# ✅ Correct: re-raise with context
try:
    risky_op()
except Exception as e:
    logger.exception("risky_op failed")
    raise CustomError("operation failed") from e

# ✅ Correct: justified silence with comment
try:
    socket.shutdown()
except OSError:
    pass  # already closed, expected after first shutdown

# ✅ Correct: catch and translate
try:
    user = User.objects.get(id=user_id)
except User.DoesNotExist:
    raise NotFoundError(f"user {user_id} not found") from None
```

## 4. 自定义异常层级

```python
class AppError(Exception):
    """应用基础异常"""
    pass

class ValidationError(AppError):
    """验证错误"""
    pass

class NotFoundError(AppError):
    """资源不存在"""
    pass

class PermissionDeniedError(AppError):
    """权限不足"""
    pass

class ExternalServiceError(AppError):
    """外部服务错误"""
    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"{service}: {message}")

# 使用
def get_user(user_id: int) -> User:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise NotFoundError(f"user {user_id} not found") from None
```

## 5. 异常链（Exception Chaining）

```python
# ❌ Wrong: 吞掉原始异常
try:
    user = db.get(User, user_id)
except DatabaseError:
    raise ServiceError("user fetch failed")

# ✅ Correct: 保留异常链
try:
    user = db.get(User, user_id)
except DatabaseError as e:
    raise ServiceError("user fetch failed") from e  # from e 保留原始异常

# ✅ Correct: 显式不保留（用 from None）
try:
    user = db.get(User, user_id)
except User.DoesNotExist:
    raise NotFoundError("user not found") from None  # 显式丢弃

# 默认情况（不写 from）：隐式链
try:
    user = db.get(User, user_id)
except DatabaseError:
    raise ServiceError("user fetch failed")  # 默认 chain，保留
```

## 6. DB Session 生命周期（规则 9）

### 模式 1: Context Manager（推荐）

```python
from sqlalchemy.orm import Session
from contextlib import contextmanager

@contextmanager
def session_scope() -> Session:
    """自动管理 session 生命周期的 context manager"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 使用
def transfer_money(from_id: int, to_id: int, amount: Decimal) -> None:
    with session_scope() as session:
        from_user = session.query(User).filter_by(id=from_id).one()
        to_user = session.query(User).filter_by(id=to_id).one()
        from_user.balance -= amount
        to_user.balance += amount
        # 退出 with 时自动 commit（无异常）或 rollback（有异常）
```

### 模式 2: try/finally（显式控制）

```python
def complex_operation() -> dict:
    session = Session()
    try:
        # 多个 step，任一失败都回滚
        user = session.query(User).filter_by(id=1).one()
        profile = session.query(Profile).filter_by(user_id=1).one()
        result = {"user": user, "profile": profile}
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()  # MUST unconditional
```

### 模式 3: FastAPI Depends（推荐用于 web）

```python
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db() -> Session:
    """FastAPI 依赖：自动管理 session"""
    db = Session()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, "user not found")
    return {"id": user.id, "name": user.name}
```

## 7. 日志记录最佳实践

```python
import logging

logger = logging.getLogger(__name__)

# ❌ Wrong: 字符串拼接（每次都执行）
logger.debug("user " + str(user_id) + " not found")

# ❌ Wrong: 总是拼接（即使日志级别关闭）
logger.info(f"user {user_id} login from {ip}")

# ✅ Correct: 延迟求值（仅在日志级别启用时执行）
logger.debug("user %s not found", user_id)

# ✅ Correct: 异常链记录
try:
    risky_op()
except Exception:
    logger.exception("risky_op failed")  # 自动包含堆栈
    raise

# ✅ Correct: 结构化日志（生产环境）
logger.info(
    "user action",
    extra={"user_id": user_id, "action": "login", "ip": ip}
)
```

## 8. 完整错误处理示例

```python
import logging
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class AppError(Exception):
    """应用基础异常"""
    pass

class NotFoundError(AppError):
    pass

class ValidationFailedError(AppError):
    pass

def get_user_profile(user_id: int, db: Session) -> dict:
    """
    获取用户档案
    
    Args:
        user_id: 用户 ID
        db: SQLAlchemy session
    
    Returns:
        用户档案字典
    
    Raises:
        NotFoundError: 用户不存在
        ValidationFailedError: 输入验证失败
    """
    # 1. 验证输入
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValidationFailedError(f"invalid user_id: {user_id}")
    
    # 2. 业务逻辑，捕获底层异常并转换
    try:
        user = db.query(User).filter_by(id=user_id).one()
    except NoResultFound:
        # 不暴露内部细节
        raise NotFoundError(f"user {user_id} not found") from None
    
    # 3. 关联数据访问
    try:
        profile = user.profile
    except AttributeError as e:
        # 罕见但可能：profile relationship 未配置
        logger.error("user %d has no profile relationship: %s", user_id, e)
        raise AppError("internal error") from e
    
    return {
        "id": user.id,
        "name": user.name,
        "profile": {
            "bio": profile.bio,
            "avatar": profile.avatar_url
        }
    }
```

## 9. 反模式速查

| 反模式 | 修复 |
|--------|------|
| `except: pass` | 删除 / 至少 log / re-raise |
| `except Exception:` 吞所有 | 改为具体异常类型 |
| `except Exception, e: pass` | log + 决定是否 re-raise |
| `session = Session()` 不关 | 用 `with` 或 try/finally |
| `raise ValueError("msg")` 不带 from | 重要场景加 `from e` 保留链 |
| `logger.info(f"user {expensive_call()}")` | 用 `%s` 占位符 |
| `if "error" in str(e):` | 用 `isinstance(e, SpecificError)` |
| `try: ... except: continue` 静默循环 | 至少 log 一次 |
| `try: ... except: return None` | 返回 Optional 让调用方处理 |
