# ArkTS vs TypeScript 差异速查

> ArkTS 是 TypeScript 的超集，但有额外约束。两者差异如下。

## 装饰器（ArkTS 独有）

ArkTS 使用装饰器声明 UI 组件生命周期：

| 装饰器 | 用途 |
|-------|------|
| `@Entry` | 页面入口（每个应用至少一个） |
| `@Component` | UI 组件 |
| `@State` | 组件私有状态 |
| `@Prop` | 父到子单向传值 |
| `@Link` | 父子双向绑定 |
| `@Watch` | 状态变化监听 |
| `@StorageLink` | AppStorage 双向绑定 |
| `@Preview` | 预览器装饰器 |

```typescript
// ArkTS 装饰器
@Entry
@Component
struct Index {
  @State count: number = 0;
}
```

```typescript
// 标准 TypeScript 没有这些装饰器
// 如在 .ts 文件中使用会报错
```

## 类型约束

### any 类型限制

```typescript
// ❌ ArkTS 禁止无类型标注
let data: any = fetchData();

// ✅ 正确：使用具体类型
interface Response {
  code: number;
  data: UserProfile;
}
let data: Response = fetchData();

// ✅ 或者 unknown + 类型守卫
let data: unknown = fetchData();
if (typeof data === 'string') {
  console.log(data.length);
}
```

### 类型字面量

```typescript
// ArkTS 支持类型字面量
type EventHandler = () => void;
type Color = string | ResourceColor;
```

## 接口与类型别名

```typescript
// ✅ ArkTS 推荐用 interface 定义对象结构
interface UserProfile {
  id: number;
  name: string;
  tags: Tag[];
}

// ✅ type alias 用于联合类型
type RequestMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';
```

## 禁止的语法

| 语法 | 说明 | 替代方案 |
|-----|------|---------|
| `any` | 禁止 | 具体类型或 `unknown` |
| `with` | 禁止 | 常规函数调用 |
| `symbol` | 禁止 | string 替代 |
| 动态属性赋值 | 受限 | 使用 `Record<string, T>` |
| `eval()` | 禁止 | HarmonyOS API |
| 索引签名 `[key: string]` | 受限 | 显式属性 |

## ArkTS 的限制（与 TypeScript 对比）

### 元数据反射

```typescript
// ❌ 禁止：TypeScript 反射 API
Reflect.getMetadata("design:paramtypes", target);

// ✅ 替代：HarmonyOS 提供了另一种方式
// 使用 @Fetch 或直接传递数据
```

### 泛型约束

```typescript
// ArkTS 泛型受限
// ❌ 不能使用 <T extends some_class>

// ✅ 可以使用接口约束
interface IUser {
  name: string;
}
function getUser<T extends IUser>(user: T): T {
  return user;
}
```

## 常用 ArkTS 模式

### 状态管理

```typescript
// 简单状态
@State message: string = 'Hello';

// 对象状态（需要用 @ObjectLink/@Observed）
@Observed
class UserState {
  name: string = '';
  age: number = 0;
}

@State userState: UserState = new UserState();
```

### 条件渲染

```typescript
// ArkTS 推荐 if/else 分支
if (this.isLoading) {
  LoadingProgress();
} else {
  Text(`Hello ${this.name}`);
}

// 不推荐三元表达式嵌套过深
```

### 循环渲染

```typescript
// ArkTS 推荐 ForEach
ForEach(
  this.items,
  (item: Item) => {
    ListItem() {
      ItemComponent({ item: item })
    }
  },
  (item: Item) => item.id.toString()  // 第二个参数是唯一键
);
```
