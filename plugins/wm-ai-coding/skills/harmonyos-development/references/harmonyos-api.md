# 常用 HarmonyOS API 示例

> 基于实际使用场景。

## HTTP 请求

### createHttp（API 9+）

```typescript
import http from '@ohos.net.http';

// 创建 HTTP 请求实例
let httpRequest = http.createHttp();

// 请求配置
let url = 'http://example.com/api/profile';

// 请求
httpRequest.request(
  url,
  {
    method: http.RequestMethod.GET,
    header: {
      'Content-Type': 'application/json'
    },
    extraData: {},
    connectTimeout: 60000,  // 60s
    readTimeout: 60000,
  },
  (err: BusinessError, data: http.HttpResponse) => {
    if (err) {
      console.error(`HTTP error: ${err.code}, ${err.message}`);
      return;
    }
    // data.result 是响应体
    console.info(`Response: ${data.result}`);
  }
);

// Promise 风格（推荐）
httpRequest.request(url, options)
  .then((resp: http.HttpResponse) => {
    if (resp.responseCode === 200) {
      let result = JSON.parse(resp.result as string);
      // 处理结果
    }
  })
  .catch((err: BusinessError) => {
    console.error(`Request failed: ${err.code}, ${err.message}`);
  })
  .finally(() => {
    // 释放请求实例
    httpRequest.destroy();
  });
```

### 上传文件

```typescript
import http from '@ohos.net.http';
import fileIO from '@ohos.file.fs';

let file = fileIO.openSync(filePath, fileIO.OpenMode.READ_ONLY);
let dataHandler = (result: number) => {
  // progress callback
};

httpRequest.requestInStream(url, {
  method: http.RequestMethod.POST,
  header: { 'Content-Type': 'multipart/form-data' },
  data: [
    { name: 'file', filePath: filePath },
  ],
}, dataHandler);
```

## 路由导航

### router.push

```typescript
import router from '@ohos.router';

// 方式1：URL 参数
router.pushUrl({
  url: 'pages/ChatDetail',
  params: {
    profileId: 123,
    name: 'Alice',
  }
});

// 方式2：接收参数
import router from '@ohos.router';

@Entry
@Component
struct ChatDetail {
  aboutToAppear(): void {
    // 获取参数
    let params = router.getParams() as Record<string, number | string>;
    let profileId = params.profileId as number;
  }
}
```

## AppStorage（全局状态）

```typescript
// 存储
AppStorage.setOrCreate('serverUrl', 'http://192.168.1.100:13000');
AppStorage.setOrCreate('authToken', 'Bearer xxx');

// 读取
let serverUrl = AppStorage.get<string>('serverUrl');
let token = AppStorage.get<string>('authToken');

// 在组件中使用 @StorageLink
@Entry
@Component
struct SettingsPage {
  @StorageLink('serverUrl') serverUrl: string = '';
}
```

## 弹窗

### promptAction.showToast

```typescript
import promptAction from '@ohos.promptAction';

// 简单提示
promptAction.showToast({
  message: '保存成功',
  duration: 2000,
});

// 带操作提示
promptAction.showToast({
  message: '是否删除？',
  duration: 3000,
  bottom: 100,
});
```

### showDialog

```typescript
import promptAction from '@ohos.promptAction';

let isConfirmed = await promptAction.showDialog({
  title: '确认删除',
  message: '删除后无法恢复，是否继续？',
  buttons: [
    { text: '取消', color: '#999999' },
    { text: '删除', color: '#FF0000' },
  ],
});

// isConfirmed.index === 0 → 取消
// isConfirmed.index === 1 → 删除
```

## 相对时间格式化

```typescript
// 格式化相对时间
function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}天前`;
  if (hours > 0) return `${hours}小时前`;
  if (minutes > 0) return `${minutes}分钟前`;
  return '刚刚';
}
```

## 日志

```typescript
import hilog from '@ohos.hilog';

// 声明 domain 和 tag
const DOMAIN = 0xFF00;
const TAG = 'ChatModule';

hilog.info(DOMAIN, TAG, 'User logged in: %{public}s', userName);
hilog.warn(DOMAIN, TAG, 'API rate limit approaching: %{public}d', count);
hilog.error(DOMAIN, TAG, 'Network error: %{public}s', err.message);
```
