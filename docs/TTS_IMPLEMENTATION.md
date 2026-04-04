# 小柔 TTS 平台感知能力实施报告

📅 **实施日期**: 2026-04-04  
🎯 **实施目标**: 增强 tts.py 的平台感知能力，解决飞书语音气泡问题  
✅ **实施状态**: 已完成

---

## 📋 问题背景

### 原始问题

用户反馈：使用小柔 skills 发语音时，飞书收到的是 MP3 文件而不是语音气泡。

**根因分析**：
1. `tts.py` 缺乏平台感知能力
2. 默认行为（MP3）在飞书上不是最优选择
3. 用户需要知道飞书需要 `.opus` 格式

---

## 🔧 实施方案

### 最佳组合：方案 1 + 方案 3 + 方案 4

| 方案 | 内容 | 状态 |
|------|------|------|
| **方案 1** | 增强 `tts.py` 平台感知能力 | ✅ 完成 |
| **方案 3** | 智能默认值（环境变量） | ✅ 完成 |
| **方案 4** | 完善文档 | ✅ 完成 |

---

## ✅ 实施详情

### 1. 代码修改

#### 修改 1：添加平台格式映射表

```python
# 平台格式映射表
CHANNEL_FORMATS = {
    'feishu': (AudioFormat.OGG_OPUS_24KHZ_MONO_32KBPS, '.opus'),
    'telegram': (AudioFormat.MP3_24000HZ_MONO_256KBPS, '.mp3'),
    'discord': (AudioFormat.MP3_24000HZ_MONO_256KBPS, '.mp3'),
    'whatsapp': (AudioFormat.OGG_OPUS_24KHZ_MONO_32KBPS, '.opus'),
}
```

#### 修改 2：添加平台格式选择函数

```python
def get_format_for_channel(channel: str, output_path: Optional[str] = None):
    """根据目标平台自动选择最优音频格式和文件后缀"""
    if channel not in CHANNEL_FORMATS:
        return None, None
    return CHANNEL_FORMATS[channel]
```

#### 修改 3：增强 text_to_speech 函数

```python
def text_to_speech(..., channel: Optional[str] = None):
    # 根据平台自动选择格式
    if channel:
        format_info, ext = get_format_for_channel(channel, output_path)
        if format_info:
            audio_format = format_info
            # 自动添加后缀
            if not any(output_path.endswith(s) for s in ['.opus', '.wav', '.mp3']):
                output_path = output_path + ext
```

#### 修改 4：添加 --channel 参数

```python
parser.add_argument('--channel', '-c', default=default_channel,
                    help='目标平台 (feishu/telegram/discord/whatsapp)，自动选择最优格式')
```

#### 修改 5：智能默认值

```python
# 从环境变量读取默认平台
default_channel = os.environ.get('AEVIA_CHANNEL', None)
```

---

### 2. 文档完善

#### 新增文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **TTS 使用指南** | `docs/TTS_GUIDE.md` | 完整使用指南、示例、故障排查 |
| **实施报告** | `docs/TTS_IMPLEMENTATION.md` | 本文档 |

#### 文档内容

- ✅ 快速开始（2 种方式）
- ✅ 参数说明
- ✅ 平台格式对照表
- ✅ 可用音色列表
- ✅ 使用示例（3 个场景）
- ✅ 注意事项
- ✅ 故障排查

---

## 📊 测试结果

### 测试场景

| 场景 | 命令 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| **飞书平台** | `--channel feishu` | 生成 OPUS | ✅ OPUS | ✅ 通过 |
| **Telegram** | `--channel telegram` | 生成 MP3 | ✅ MP3 | ✅ 通过 |
| **智能默认** | `export AEVIA_CHANNEL=feishu` | 生成 OPUS | ✅ OPUS | ✅ 通过 |
| **向后兼容** | 不指定 channel | 根据后缀 | ✅ 正常 | ✅ 通过 |
| **飞书气泡** | OPUS 格式发送 | 语音气泡 | ✅ 气泡 | ✅ 通过 |

### 测试详情

#### 测试 1：飞书平台

```bash
$ python3 tts.py "我好想你呀" /tmp/test --channel feishu
INFO - 自动添加文件后缀：/tmp/test.opus
INFO - ✓ 语音生成成功 (7093 bytes)

$ file /tmp/test.opus
Ogg data, Opus audio
```

#### 测试 2：智能默认值

```bash
$ export AEVIA_CHANNEL=feishu
$ python3 tts.py "测试智能默认值" /tmp/test
INFO - 自动添加文件后缀：/tmp/test.opus
INFO - ✓ 语音生成成功 (9668 bytes)
```

#### 测试 3：向后兼容

```bash
$ python3 tts.py "测试" /tmp/test.opus
INFO - ✓ 语音生成成功
INFO - ✓ OPUS 格式验证通过
```

---

## 🎯 改进效果

### 用户体验改进

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| **飞书语音** | 需要知道用 OPUS | 只需 `--channel feishu` |
| **多平台** | 需要手动切换格式 | 自动选择最优格式 |
| **默认行为** | 固定 MP3 | 根据环境变量智能选择 |
| **学习成本** | 需要了解各平台格式 | 只需记住平台名称 |

### 代码质量改进

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| **平台感知** | ❌ 无 | ✅ 完整支持 |
| **智能默认** | ❌ 无 | ✅ 环境变量 |
| **向后兼容** | ✅ 是 | ✅ 保持 |
| **文档完善度** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 📋 使用方式对比

### 改进前

```bash
# 用户需要知道飞书需要 OPUS
python3 tts.py "早上好" /tmp/voice.opus

# 或者错误地使用 MP3
python3 tts.py "早上好" /tmp/voice.mp3  # ❌ 飞书当普通文件
```

### 改进后

```bash
# 方式 1：使用 --channel（推荐）
python3 tts.py "早上好" /tmp/voice --channel feishu  # ✅ 自动 OPUS

# 方式 2：使用环境变量（推荐）
export AEVIA_CHANNEL=feishu
python3 tts.py "早上好" /tmp/voice  # ✅ 自动 OPUS

# 方式 3：向后兼容
python3 tts.py "早上好" /tmp/voice.opus  # ✅ 保持兼容
```

---

## 🚀 后续建议

### 短期（已完成）

- [x] 增强 `tts.py` 平台感知能力
- [x] 智能默认值（环境变量）
- [x] 完善文档

### 中期（可选）

- [ ] 在 `aevia.sh` 中默认传递 `--channel` 参数
- [ ] 添加平台格式验证工具
- [ ] 集成到 CI/CD 自动测试

### 长期（可选）

- [ ] 支持更多平台（微信、钉钉等）
- [ ] 支持更多音频格式
- [ ] 添加音频质量选择（比特率、采样率）

---

## 📚 相关资源

- **代码位置**: `skills/xiaorou/scripts/tts.py`
- **使用指南**: `skills/xiaorou/docs/TTS_GUIDE.md`
- **统一入口**: `skills/xiaorou/scripts/aevia.sh`

---

**实施者**: 小柔 AI Team 🦞  
**审核者**: Claude Code  
**完成时间**: 2026-04-04 21:46
