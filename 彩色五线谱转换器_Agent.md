# 彩色五线谱转换器 — 开发 Agent 文档

> 一键复制本文档给 AI 助手，即可完整理解项目架构、逻辑规则、历史问题和调试方法，继续开发或修复。

---

## 一、项目概述

**目标**：将黑白 MusicXML 五线谱自动转换为彩色标注乐谱，帮助演奏者快速识别升降号并弹对琴键。

**核心规则**：
- 全音升号（有黑键，如 F♯ C♯ G♯ D♯ A♯）→ 品红色 `#FF00FF`，弹右侧黑键
- 全音降号（有黑键，如 G♭ D♭ A♭ E♭ B♭）→ 蓝色 `#0000FF`，弹左侧黑键
- 半音升号（E♯→F, B♯→C）→ 黑色，替换为实际音高
- 半音降号（F♭→E, C♭→B）→ 黑色，替换为实际音高
- 重升 × → 黑色 + 红色 45° 斜线标记
- 重降 ♭♭ → 黑色 + 蓝色 45° 斜线标记
- 调号保留，临时变音记号删除
- 多声部独立处理

**输入**：`.xml` / `.musicxml` / `.mxl`（压缩 MusicXML）
**输出**：SVG（浏览器预览）+ PNG 下载

---

## 二、项目结构

```
d:\trae_work_pdf\color_sheet_music\
├── app.py                  # Flask Web 服务（主入口）
├── converter.py            # 主转换管线，含子进程渲染调用
├── render_worker.py        # Verovio 渲染子进程（独立进程，避免字体问题）
├── color_engine.py         # 颜色规则引擎（核心乐理逻辑）
├── musicxml_processor.py   # MusicXML 解析与颜色注入
├── svg_postprocessor.py    # SVG 斜线标记后处理
├── templates/
│   └── index.html          # Web 前端页面
├── outputs/                # 输出文件目录（SVG/PNG）
├── uploads/                # 上传文件临时目录
├── test_score.xml          # 测试用 MusicXML
├── test_convert_api.py     # API 测试脚本
├── test_pages.py           # 分页测试脚本
├── test_color_engine.py    # 颜色引擎单元测试
└── __pycache__/            # Python 缓存（每次修改代码后需删除）
```

---

## 三、核心模块详解

### 3.1 `color_engine.py` — 颜色规则引擎

**半音/全音判断**：
- 自然半音对（白键之间无黑键）：`E→F`、`B→C`（上行），`F→E`、`C→B`（下行）
- `is_whole_tone_up(step)`：不在 `NATURAL_SEMITONE_UP` 中即为全音
- `is_whole_tone_down(step)`：不在 `NATURAL_SEMITONE_DOWN` 中即为全音

**等音计算** `get_enharmonic_equivalent(step, alter)`：
- 将音名 + alter 转为实际半音值（0-11），再反向查表
- 返回 `(new_step, new_alter, octave_shift)`

**核心函数** `analyze_note(step, octave, alter, key_fifths)`：
- 返回 `{step, octave, color, action, mark}`
- `action` 取值：`keep`（标色）/ `replace`（换音高）/ `replace_with_mark`（换音高+斜线）
- `mark` 取值：`None` / `red_diagonal` / `blue_diagonal`

### 3.2 `musicxml_processor.py` — MusicXML 处理

**处理流程**：
1. 解析 XML，检测命名空间
2. 遍历每个 part → measure → note
3. 跟踪每小节的临时变音表 `{(step, octave, voice): alter}`（跨小节自动清除）
4. 对每个音符调用 `color_engine.analyze_note()`
5. 根据结果修改 XML：改音高、删 accidental、加 color 属性

**关键细节**：
- 括号变音记号（`parentheses="yes"`）视为提示性，忽略
- 调号变音（key signature）通过 `get_key_signature_note_alter()` 获取
- 重升/重降的替换音符通过自定义属性 `{http://color-sheet-music}mark` 传递

### 3.3 `render_worker.py` — Verovio 渲染子进程

**为什么用子进程**：Flask 进程内直接调用 Verovio 会因字体路径问题（Linux 路径 `/usr/local/share/verovio`）输出空 SVG（0px）。子进程独立运行不受影响。

**渲染选项**：
```python
'pageWidth': 2100, 'pageHeight': 2970, 'scale': 40,
'adjustPageWidth': True, 'footer': 'none',
# 注意：不要加 'header': 'none'，否则标题/作曲家丢失
```

**多页合并逻辑** `_combine_pages(pages)`：
1. 逐页渲染 SVG
2. 提取所有页的 `<defs>` 中缺失的 glyph 定义合并到第一页（关键！否则跨页 glyph 丢失）
3. 收集所有 `page-margin` 组，按 y 偏移重新排列
4. 更新 viewBox 和外层 SVG 高度

### 3.4 `svg_postprocessor.py` — 斜线标记

- `find_marks_in_processed_musicxml()`：从处理后的 XML 提取斜线标记列表
- `add_diagonal_marks()`：在 SVG 的 note 元素上叠加 45° 斜线

### 3.5 `converter.py` — 主转换管线

**`convert_musicxml_to_colored_svg(xml_string)`**：
1. `musicxml_processor.process_musicxml()` → 处理后的 XML
2. `find_marks_in_processed_musicxml()` → 斜线标记列表
3. `_render_via_subprocess()` → 子进程调用 Verovio 渲染 SVG
4. `_fix_svg_dimensions()` → 修复 0px 尺寸（仅当实际为 0 时）
5. `add_diagonal_marks()` → 叠加斜线

**`_render_via_subprocess(xml_string)`**：
- 写临时 XML 文件 → subprocess.run → 读临时 SVG 文件
- 超时：120 秒
- 子进程执行：`python render_worker.py <xml_path> <svg_path>`

### 3.6 `app.py` — Flask Web 服务

**端点**：
- `GET /` → 上传页面
- `POST /api/convert` → 上传文件，返回 SVG base64
- `GET /api/download/<filename>` → 下载文件
- `GET /api/test_vrv` → 测试 Verovio 状态

**文件上传处理**：
- `.mxl`：用 zipfile 解压，从 `META-INF/container.xml` 找根文件
- `.xml` / `.musicxml`：直接 UTF-8 解码
- 限制：16MB

### 3.7 `templates/index.html` — 前端

- 拖拽或点击上传
- SVG 直接 `<img>` 预览
- PNG 下载：前端 Canvas 转换（不依赖 Cairo）

---

## 四、历史问题与修复记录

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | `.mxl` 上传报错"文件编码错误" | `.mxl` 是 ZIP 二进制，被当作 UTF-8 解码 | 先读 raw bytes，检测 `.mxl` 扩展名后走 zipfile 解压 |
| 2 | PNG 下载无反应 | Windows 无 Cairo 库，`cairosvg` 不可用 | 前端 Canvas API 转换 SVG→PNG |
| 3 | SVG 预览空白（0px） | Flask 进程中 Verovio 字体路径为 Linux 路径，找不到字体 | 改用子进程 `render_worker.py` 独立渲染 |
| 4 | 子进程方案不生效 | `__pycache__` 缓存未清除，Flask 运行旧代码 | 每次修改后：`Stop-Process python -Force` + 删除 `__pycache__/` + 重启 |
| 5 | 只转换 21 小节（原 34 小节） | Verovio 默认分页，只渲染第一页 | 改为分页渲染 + `_combine_pages()` 合并 |
| 6 | 合并后所有小节变成一行 | 无分页断行，超宽 SVG | 移除 `breaks: 'none'`，恢复标准页面尺寸按原谱分页 |
| 7 | 最后一小节全音符丢失 | 合并时只用了 Page 1 的 defs，Page 2 独有的 `E0A2` glyph 缺失 | `_combine_pages()` 中添加 defs 合并逻辑 |
| 8 | 标题/作曲家/作品号丢失 | 设置了 `'header': 'none'` | 移除该选项 |
| 9 | 图例遮挡五线谱 | 图例 `rect` 放在根 SVG 而非 `legend_g` 内，固定在 (0,0) | 将 `rect` 移入 `legend_g` 组内（后直接删除整个图例） |
| 10 | 图例影响美观 | 用户要求删除 | 移除 `add_legend_to_svg()` 调用 |

---

## 五、调试速查

### 启动服务
```powershell
cd d:\trae_work_pdf\color_sheet_music
# 先清理缓存和残留进程
Stop-Process -Name python -Force 2>$null
Remove-Item -Recurse -Force __pycache__ 2>$null
# 启动
python app.py
```

### 测试 API
```powershell
python test_convert_api.py
# 或修改 test_convert_api.py 中的文件路径测试不同乐谱
```

### 测试 Verovio 分页
```powershell
python test_pages.py
```

### 测试渲染子进程独立运行
```powershell
python render_worker.py outputs\test.xml outputs\test_out.svg
```

### 检查输出 SVG 元素
```powershell
python compare_score.py
```

### 关键检查点
- 转换后小节数：`Select-String -Path outputs\*.svg -Pattern 'class="measure"' | Measure-Object`
- 分页数：`Select-String -Path outputs\*.svg -Pattern 'class="page-margin"' | Measure-Object`
- 彩色标注数：`Select-String -Path outputs\*.svg -Pattern 'color="#FF00FF"|color="#0000FF"' | Measure-Object`
- 标题信息：`Select-String -Path outputs\*.svg -Pattern 'Prelude|Bach|BWV'`

---

## 六、依赖

```
flask
lxml
verovio
requests  # 仅测试用
```

安装：`pip install flask lxml verovio requests`

---

## 七、架构决策记录

1. **Verovio 子进程隔离**：因 Flask 进程内 Verovio 字体加载失败（Windows 上默认 resource_path 指向 Linux 路径），所有渲染必须通过 `render_worker.py` 子进程完成
2. **多页纵向堆叠**：Verovio 按原始 MusicXML 分页断行，前端合并为单 SVG 纵向堆叠显示，每个 page-margin 通过 `transform: translate()` 偏移定位
3. **defs 跨页合并**：Verovio 每页只定义本页使用的 glyph，合并时必须扫描所有页的 defs 并补充缺失的 glyph 定义到第一页
4. **不渲染图例**：用户要求删除，当前输出纯谱面 SVG
5. **前端 PNG 转换**：不依赖 Cairo，用 Canvas API 实现跨平台兼容