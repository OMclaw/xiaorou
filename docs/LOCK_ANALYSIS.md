# 🔒 锁机制并发场景分析报告

## 📋 测试场景
**场景描述**: 机器人持续用多张图片测试图生图功能（高频并发调用）

---

## 1️⃣ 现有锁机制总结

### 1.1 文件锁（防并发刷屏）
- **位置**: `scripts/selfie.py` `__main__` 入口
- **文件**: `/tmp/xiaorou/selfie_task.lock`
- **超时**: 300 秒 (5 分钟)
- **类型**: `fcntl.flock()` 独占锁
- **修复历史**:
  - v5.3.0: 初始实现（atexit 清理）
  - v5.22.1: 添加过期检查（防止异常退出后残留）

### 1.2 线程锁（并发安全）
| 锁名称 | 位置 | 用途 |
|--------|------|------|
| `Config._lock` | config.py:57 | 单例模式 + 配置缓存 (RLock) |
| `_feishu_token_lock` | selfie.py:63 | 飞书 token 并发刷新保护 |
| `_tts_lock` | tts.py:31 | TTS 生成并发保护 |

---

## 2️⃣ 并发场景分析

### 2.1 场景 1: 单进程串行调用 ✅
```bash
# 用户连续发送多条消息
消息 1 → selfie.py → 完成
消息 2 → selfie.py → 完成
消息 3 → selfie.py → 完成
```
**状态**: ✅ 正常工作，每个任务独立执行

### 2.2 场景 2: 多进程并发调用 ⚠️
```bash
# 机器人同时处理多个用户请求
进程 1 → selfie.py → 获取文件锁 → 执行
进程 2 → selfie.py → 获取锁失败 → 退出 (Task is already running)
进程 3 → selfie.py → 获取锁失败 → 退出 (Task is already running)
```
**问题**: 
- ❌ 后续任务被跳过，用户收不到回复
- ✅ 防止刷屏（设计目标）
- ⚠️ **5 分钟超时内，只有第一个任务执行**

### 2.3 场景 3: 快速连续调用（<5 分钟间隔） ⚠️
```bash
T=0s   → 任务 1 启动 → 获取锁 → 执行 20 秒 → 释放锁
T=30s  → 任务 2 启动 → 检查锁已过期 → 清理 → 获取锁 → 执行
T=60s  → 任务 3 启动 → 检查锁已过期 → 清理 → 获取锁 → 执行
```
**状态**: ✅ 正常工作（修复后）

### 2.4 场景 4: 进程异常退出 🐛
```bash
任务 1 启动 → 获取锁 → 进程被 kill -9/OOM → 锁文件残留
任务 2 启动 → 检查锁文件 mtime → 5 分钟内 → 跳过
5 分钟后 → 任务 3 启动 → 检测到过期 → 清理 → 执行
```
**修复前**: ❌ 永久阻塞
**修复后**: ✅ 5 分钟后自动恢复

---

## 3️⃣ 潜在问题识别

### 🔴 P0 问题

#### 问题 1: 5 分钟超时内无法处理并发请求
**影响**: 高频测试场景下，90% 的请求会被跳过

**场景**:
```bash
# 机器人 1 秒内收到 10 张图片
T=0s  → 请求 1 → 获取锁 → 执行（20 秒）
T=1s  → 请求 2 → 锁未过期 → 跳过 ❌
T=2s  → 请求 3 → 锁未过期 → 跳过 ❌
...
T=300s → 锁过期 → 请求 11 才能执行
```

**建议修复**:
- 降低超时时间：300 秒 → 30 秒（单次任务最长 20 秒）
- 或：改用队列机制，不跳过而是排队

### 🟡 P1 问题

#### 问题 2: 锁文件检查竞态条件
**代码**:
```python
if not is_lock_expired(LOCK_FILE, timeout_seconds=300):
    sys.exit(0)

if os.path.exists(LOCK_FILE):
    os.remove(LOCK_FILE)  # ← 竞态条件

lock_fd = open(LOCK_FILE, 'w')
fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
```

**问题**: 两个进程可能同时检测到过期，同时删除，然后只有一个能获取锁

**影响**: ⚠️ 轻微，最坏情况一个进程被跳过（可接受）

#### 问题 3: 线程锁未覆盖图片生成过程
**代码**:
```python
def generate_images_single_model(...):
    model_result = generate_single_image(...)  # ← 无锁保护
```

**影响**: 
- ✅ API 调用本身线程安全（DashScope SDK）
- ⚠️ 但多个线程可能同时写入同一临时文件

### 🟢 P2 问题

#### 问题 4: 临时文件命名冲突
**代码**:
```python
latest_selfie = f"/tmp/xiaorou/selfie_latest_{user_id}.jpg"
```

**场景**: 同一用户并发发送 2 张图片
```bash
线程 1 → 生成中 → 写入 selfie_latest_ou_xxx.jpg (20 秒)
线程 2 → 生成中 → 覆盖写入 selfie_latest_ou_xxx.jpg (20 秒)
结果：文件内容可能是混合的
```

**建议**: 使用唯一文件名（UUID/时间戳）

#### 问题 5: 飞书 token 缓存竞态
**代码**:
```python
_feishu_token: Optional[str] = None  # 全局变量
_feishu_token_lock = threading.Lock()
```

**影响**: ✅ 已有锁保护，但仅在同一进程内有效
**问题**: ❌ 多进程场景下，每个进程独立缓存，可能同时刷新

---

## 4️⃣ 优化建议

### 4.1 高频并发场景优化（P0）

**方案 A: 降低超时时间**
```python
# 修改：300 秒 → 30 秒
if not is_lock_expired(LOCK_FILE, timeout_seconds=30):
```

**优点**: 
- ✅ 简单，改动最小
- ✅ 30 秒足够单次任务（20 秒生成 +10 秒发送）

**缺点**:
- ⚠️ 进程崩溃后，30 秒内仍可能重复执行

**方案 B: 改用队列机制**
```python
# 不跳过，而是等待
lock_fd = open(LOCK_FILE, 'w')
fcntl.flock(lock_fd, fcntl.LOCK_EX)  # 阻塞等待，不返回
```

**优点**:
- ✅ 所有请求都会执行
- ✅ 有序排队，不会丢失

**缺点**:
- ⚠️ 用户等待时间不确定
- ⚠️ 可能堆积大量任务

**方案 C: 分布式锁（Redis）**
```python
import redis
r = redis.Redis()
if r.set('xiaorou:lock', '1', nx=True, ex=300):
    # 获取锁成功
```

**优点**:
- ✅ 支持多进程/多机
- ✅ 原子操作，无竞态

**缺点**:
- ⚠️ 需要 Redis 依赖
- ⚠️ 增加复杂度

### 4.2 临时文件命名优化（P2）

**当前**:
```python
latest_selfie = f"/tmp/xiaorou/selfie_latest_{user_id}.jpg"
```

**建议**:
```python
import uuid
latest_selfie = f"/tmp/xiaorou/selfie_{user_id}_{uuid.uuid4().hex[:8]}.jpg"
```

### 4.3 日志优化（P2）

**当前**: 锁跳过时只打印一行
```python
print("Task is already running. Skipping to prevent spam.")
```

**建议**: 记录详细日志
```python
logger.warning(f"检测到并发请求，跳过执行（锁文件：{LOCK_FILE}）")
```

---

## 5️⃣ 测试建议

### 5.1 压力测试脚本
```bash
#!/bin/bash
# 并发测试：1 秒内发送 10 个请求
for i in {1..10}; do
    python3 scripts/selfie.py --reference /tmp/test_$i.jpg feishu "" "" &
done
wait
```

### 5.2 验证检查点
- [ ] 10 个请求中，几个执行成功？
- [ ] 锁文件是否正确清理？
- [ ] 临时文件是否冲突？
- [ ] 日志是否清晰？

---

## 6️⃣ 总结

### 当前状态
| 问题 | 严重度 | 状态 |
|------|--------|------|
| 锁文件残留 | P0 | ✅ 已修复 (v5.22.1) |
| 5 分钟超时阻塞 | P0 | ⚠️ 待优化 |
| 临时文件命名冲突 | P2 | ⚠️ 待修复 |
| 飞书 token 多进程缓存 | P2 | ⚠️ 待优化 |

### 建议优先级
1. **P0**: 降低超时时间（300 秒 → 30 秒）
2. **P2**: 临时文件 UUID 命名
3. **P2**: 日志增强

---

**生成时间**: 2026-04-12
**版本**: v5.22.1
