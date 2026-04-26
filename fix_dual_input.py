#!/usr/bin/env python3
"""修改 selfie_v2.py 为双图输入模式"""

with open('scripts/selfie_v2.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip_until_channel = False

for i, line in enumerate(lines):
    # 跳过图 2-2 相关代码
    if '# 加载图 2-2（多角度参考）' in line:
        skip_until_channel = True
        new_lines.append('        # 双图输入模式，不使用图 2-2\n')
        new_lines.append('        use_three_images = False\n')
        continue
    
    if skip_until_channel:
        if 'channel = validate_channel(channel)' in line:
            skip_until_channel = False
        else:
            continue
    
    # 修改图 2-1 日志
    if '图 2-1 验证通过（正脸参考）' in line:
        line = line.replace('图 2-1 验证通过（正脸参考）', '图 2 验证通过（人物正脸）')
    
    # 修改三图/双图判断
    if '# 三图/双图输入生成' in line:
        line = '        # 双图输入生成\n'
    
    if 'if use_three_images:' in line:
        continue
    
    if 'generate_role_swap_image_three' in line:
        continue
    
    if '三图输入：参考图 + 图 2-1 + 图 2-2' in line:
        line = '        logger.info("🚀 wan2.7-image 生成中 (双图输入：参考图 + 图 2)...")\n'
    
    if '三图/双图输入' in line and '角色替换模式' in line:
        line = line.replace('双图或三图输入', '双图输入')
    
    if '小柔在参考图场景下' in line and '角色替换模式' in line:
        line = line.replace('小柔在参考图场景下', '人物在参考图场景下')
    
    new_lines.append(line)

with open('scripts/selfie_v2.py', 'w') as f:
    f.writelines(new_lines)

print("✅ 修改完成 - 双图输入模式")
