# ArkTS 状态管理最佳实践

本文件为 OpenSpec `languages-arkts/spec.md` 中 3 条 @State 相关规则（HARD-GATE 3、4、6）提供**可复用代码模板**。每个模式包含：触发场景、错误示例、正确示例。

---

## 1. @State 对象更新模式（对应 HARD-GATE 3）

### 适用场景

任何 `@State` 对象的属性变更，包括基本对象和嵌套对象。

### 错误示例 ❌

```typescript
// ❌ 直接属性赋值 — ArkTS 不会触发 UI 更新
@State profile: Profile = { name: '', age: 0 };

async loadProfile() {
  const data = await ApiService.getProfile();
  this.profile.name = data.name;   // ❌ UI 不更新
  this.profile.age = data.age;     // ❌ UI 不更新
}

// ❌ 修改嵌套对象
this.profile.address.city = 'Beijing';  // ❌ UI 不更新
```

### 正确示例 ✅

```typescript
// ✅ 整体替换 — ArkTS 检测到引用变化，触发 UI 更新
@State profile: Profile = { name: '', age: 0, address: { city: '' } };

async loadProfile() {
  const data = await ApiService.getProfile();
  this.profile = { ...this.profile, name: data.name, age: data.age };
}

// ✅ 嵌套对象 — 必须构造完整新对象
this.profile = {
  ...this.profile,
  address: { ...this.profile.address, city: 'Beijing' }
};
```

### 关键点

- ArkTS `@State` 通过引用变化触发 UI 更新（浅比较）
- 直接属性赋值不改变引用 → UI 不更新
- 嵌套对象必须逐层构造新对象

---

## 2. @State 数组更新模式（对应 HARD-GATE 4）

### 适用场景

任何 `@State` 数组的增删改查。

### 错误示例 ❌

```typescript
// ❌ push 添加 — 不触发 UI 更新
@State items: Item[] = [];

addItem(newItem: Item) {
  this.items.push(newItem);  // ❌ UI 不更新
}

// ❌ splice 删除 — 不触发 UI 更新
removeItem(id: number) {
  const index = this.items.findIndex(i => i.id === id);
  this.items.splice(index, 1);  // ❌ UI 不更新
}

// ❌ pop 删除末尾
this.items.pop();  // ❌ UI 不更新

// ❌ 索引赋值修改
this.items[0] = newItem;  // ❌ UI 不更新
```

### 正确示例 ✅

```typescript
// ✅ 添加 — 创建新数组
addItem(newItem: Item) {
  this.items = [...this.items, newItem];
}

// ✅ 删除 — 用 filter 创建新数组
removeItem(id: number) {
  this.items = this.items.filter(i => i.id !== id);
}

// ✅ 修改 — 用 map 创建新数组
updateItem(id: number, updates: Partial<Item>) {
  this.items = this.items.map(i =>
    i.id === id ? { ...i, ...updates } : i
  );
}

// ✅ 清空
this.items = [];

// ✅ 排序
this.items = [...this.items].sort((a, b) => a.order - b.order);
```

### 关键点

- 所有变更都需创建**新数组引用**
- `filter` / `map` / 扩展运算符是最常用的不可变操作
- 复杂排序可以先 `[...arr]` 浅拷贝再 `.sort()`

---

## 3. @Observed + @ObjectLink 嵌套对象模式（SHOULD）

### 适用场景

当 `@State` 对象内部有嵌套对象，且需要直接修改嵌套属性时。

### 错误示例 ❌

```typescript
// ❌ 嵌套对象直接修改不触发 UI 更新
@State user: User = { name: 'Tom', address: { city: 'Beijing' } };

changeCity() {
  // 即使用扩展运算，嵌套对象引用未变
  this.user = { ...this.user, address: { ...this.user.address, city: 'Shanghai' } };
  // 这种写法可行但繁琐，需要逐层展开
}
```

### 正确示例 ✅

```typescript
// ✅ 用 @Observed 标记嵌套类，@ObjectLink 引用
@Observed
class Address {
  city: string = '';
  street: string = '';
}

@Observed
class User {
  name: string = '';
  @ObjectLink address: Address;  // 注意：是 @ObjectLink 不是 @State
}

@Entry
@Component
struct ProfilePage {
  @State user: User = new User();
  // address 由父组件传入或初始化
  @State address: Address = new Address();

  aboutToAppear() {
    // 初始化时绑定
    this.user.address = this.address;
  }

  build() {
    Column() {
      // 修改嵌套属性会触发 UI 更新
      Button('Change City').onClick(() => {
        this.user.address.city = 'Shanghai';  // ✅ 触发 UI 更新
      })
    }
  }
}
```

### 关键点

- `@Observed` 装饰的类，其属性变更会被 ArkTS 深度监听
- `@ObjectLink` 是引用，不是 `@State`
- 适用于**复杂嵌套数据结构**（如表单、列表项内部状态）
- 简单场景用扩展运算符即可

---

## 4. ForEach key 函数最佳实践（SHOULD）

### 适用场景

任何使用 `ForEach` 渲染列表的场景。

### 错误示例 ❌

```typescript
// ❌ 无 key 函数 — 列表项复用错乱
ForEach(this.items,
  (item: Item) => ItemRow({ item: item })
);
```

### 正确示例 ✅

```typescript
// ✅ 提供稳定唯一键
ForEach(this.items,
  (item: Item) => ItemRow({ item: item }),
  (item: Item) => item.id.toString()  // 用 item.id 作为 key
);

// ✅ 复杂对象可用组合键
ForEach(this.contacts,
  (contact: Contact) => ContactCard({ contact: contact }),
  (contact: Contact) => `${contact.userId}_${contact.tag}`
);
```

### 关键点

- key 必须是**稳定且唯一**的（不能是数组索引）
- 优先用业务 ID（`item.id`）
- 复杂场景可用组合键（`userId_tag`）

---

## 5. 完整状态管理模式示例

```typescript
@Entry
@Component
struct TodoListPage {
  @State todos: Todo[] = [];
  @State loading: boolean = false;
  @State error: string = '';
  @State newTodoText: string = '';

  async aboutToAppear() {
    this.loading = true;
    try {
      this.todos = await TodoService.list();
    } catch (e) {
      logger.error('TodoList', `加载失败: ${JSON.stringify(e)}`);
      this.error = '加载失败，请重试';
      showToast({ message: '加载失败' });
    } finally {
      this.loading = false;
    }
  }

  addTodo() {
    if (!this.newTodoText.trim()) return;
    const newTodo: Todo = {
      id: Date.now().toString(),
      text: this.newTodoText,
      done: false
    };
    this.todos = [...this.todos, newTodo];  // ✅ 数组扩展
    this.newTodoText = '';
  }

  toggleTodo(id: string) {
    this.todos = this.todos.map(t =>  // ✅ 数组 map
      t.id === id ? { ...t, done: !t.done } : t
    );
  }

  deleteTodo(id: string) {
    this.todos = this.todos.filter(t => t.id !== id);  // ✅ 数组 filter
  }

  build() {
    Column() {
      TextInput({ text: this.newTodoText })
        .onChange((v: string) => { this.newTodoText = v; })
      Button('Add').onClick(() => this.addTodo())

      if (this.loading) {
        LoadingProgress()
      } else {
        List() {
          ForEach(this.todos,
            (todo: Todo) => ListItem() {
              Row() {
                Text(todo.text)
                Button(todo.done ? 'Undo' : 'Done').onClick(() => this.toggleTodo(todo.id))
                Button('Delete').onClick(() => this.deleteTodo(todo.id))
              }
            },
            (todo: Todo) => todo.id  // ✅ 稳定 key
          )
        }
      }
    }
  }
}
```
