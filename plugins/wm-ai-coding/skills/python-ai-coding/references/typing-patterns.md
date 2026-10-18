# Python 类型注解模式

本文件为 OpenSpec `languages-python/spec.md` 中规则 1、7、8（Type Hints / 类型注解 / Any 替代）提供**可复用代码模板**。

---

## 1. 基础类型注解

```python
# ✅ 标准用法
name: str = "Alice"
age: int = 30
price: float = 9.99
is_active: bool = True

# ✅ 容器类型（Python 3.9+ 内置泛型）
items: list[str] = []
mapping: dict[str, int] = {}
unique_ids: set[int] = set()
coordinates: tuple[float, float] = (0.0, 0.0)
```

## 2. Optional / Union / None 默认值

```python
from typing import Optional, Union

# ✅ Optional[T] = Union[T, None]
def find_user(name: str) -> Optional[User]:
    """Returns User if found, None otherwise."""
    return User.objects.filter(name=name).first()

# ✅ None 默认值 MUST 标注为 Optional
def greet(name: Optional[str] = None) -> str:
    if name is None:
        return "Hello, stranger!"
    return f"Hello, {name}!"

# ✅ Union 用于多类型
def parse_value(raw: Union[str, int, float]) -> float:
    return float(raw)
```

## 3. Generic 类型

```python
from typing import TypeVar, Generic, List

T = TypeVar("T")

class Repository(Generic[T]):
    def find_all(self) -> List[T]:
        return self._query_all()

    def find_by_id(self, id: int) -> Optional[T]:
        return self._query_by_id(id)

# 使用
user_repo: Repository[User] = Repository[User]()
profile_repo: Repository[Profile] = Repository[Profile]()
```

## 4. 替换 Any 的 4 种模式

### 模式 1: 用具体类型

```python
# ❌ Wrong
def process(data: Any) -> Any:
    return data

# ✅ Correct
def process(data: Profile) -> Profile:
    return data
```

### 模式 2: 用 Union

```python
# ❌ Wrong
def parse(input: Any) -> Any:
    return json.loads(input) if isinstance(input, str) else input

# ✅ Correct
def parse(input: Union[str, bytes, dict]) -> Any:
    """Note: 返回 Any 是合理的（JSON 反序列化结果未知）"""
    if isinstance(input, (str, bytes)):
        return json.loads(input)
    return input
```

### 模式 3: 用 Generic + TypeVar

```python
T = TypeVar("T")

# ❌ Wrong
def first(items: list) -> Any:
    return items[0]

# ✅ Correct
def first(items: list[T]) -> T:
    return items[0]
```

### 模式 4: Protocol（结构化类型）

```python
from typing import Protocol

class HasName(Protocol):
    name: str

# ❌ Wrong
def greet(obj: Any) -> str:
    return f"Hello, {obj.name}"

# ✅ Correct
def greet(obj: HasName) -> str:
    return f"Hello, {obj.name}"
```

## 5. Callable 类型

```python
from typing import Callable

# ✅ 接受回调
def retry(times: int, fn: Callable[[], None]) -> None:
    for _ in range(times):
        try:
            fn()
            return
        except Exception:
            continue
    raise RuntimeError(f"failed after {times} attempts")

# ✅ 复杂回调签名
Handler = Callable[[str, int], Optional[dict]]
def register(name: str, handler: Handler) -> None:
    ...
```

## 6. 常见错误与修复

```python
# ❌ Wrong: 忘记 import
def f(x: int) -> str:  # NameError: name 'int' is not defined (Python 3.9 之前)
    return str(x)

# ✅ Correct: Python 3.9+ 内置类型可直接使用，无需 import
def f(x: int) -> str:
    return str(x)

# ❌ Wrong: 类型注解与实际不符
def f(items: list[int]) -> int:
    return items[0]  # mypy: List item 0 is int, OK；但若改成 return items，错误

# ✅ Correct: 类型必须与实现一致
def f(items: list[int]) -> int:
    if not items:
        raise ValueError("empty list")
    return items[0]
```

## 7. mypy 配置示例

```ini
# mypy.ini
[mypy]
python_version = 3.11
strict = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
```
