# 彩色五线谱转换器 — 完整复原提示词

> 版本日期：2026-07-16
> 将此提示词交给 AI（如 Claude、GPT-4 等），可 100% 复原整个项目。

---

## 任务

请严格按照以下规格，在 `d:\trae_work_pdf\color_sheet_music\` 目录下创建完整的"彩色五线谱转换器"项目。

---

## 项目概述

一个 Web 应用，用户上传 MusicXML 乐谱文件（.xml / .musicxml / .mxl），系统自动将升号音标注为品红色、降号音标注为蓝色，输出分页 SVG 和 PNG，支持多页预览、分页下载、ZIP 批量下载。

---

## 技术栈

- Python 3.11 + Flask
- Verovio 4.x（MusicXML → SVG 渲染引擎）
- lxml（XML/SVG 处理）
- 前端：纯 HTML/CSS/JS，无框架

---

## 文件结构

```
color_sheet_music/
├── app.py                  # Flask Web 服务
├── color_engine.py         # 颜色规则引擎
├── converter.py            # 主转换管线
├── musicxml_processor.py   # MusicXML 解析与颜色注入
├── render_worker.py        # Verovio 渲染子进程
├── svg_postprocessor.py    # SVG 后处理（符头颜色迁移）
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 部署
├── fly.toml                # Fly.io 部署配置
├── .gitignore
├── .dockerignore
├── templates/
│   └── index.html          # 前端页面
├── outputs/                # 输出临时文件（运行时自动创建）
├── uploads/                # 上传临时文件（运行时自动创建）
├── dev_logs/               # 开发日志（运行时按需创建）
└── prompts/                # 复原提示词（运行时按需创建）
```

---

## 文件 1：`requirements.txt`

```
Flask>=3.0
verovio>=4.0
lxml>=5.0
gunicorn>=21.0
```

---

## 文件 2：`color_engine.py`

```python
"""
彩色五线谱颜色规则引擎
判断每个音符的全音/半音关系，决定颜色标注方案
"""

NATURAL_SEMITONE_UP = {'E': 'F', 'B': 'C'}
NATURAL_SEMITONE_DOWN = {'F': 'E', 'C': 'B'}
NOTE_ORDER = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F']

COLOR_RED = '#FF00FF'
COLOR_BLUE = '#0000FF'
COLOR_BLACK = '#000000'


def get_note_index(step: str) -> int:
    return NOTE_ORDER.index(step.upper())


def get_note_above(step: str) -> str:
    idx = get_note_index(step)
    return NOTE_ORDER[(idx + 1) % 7]


def get_note_below(step: str) -> str:
    idx = get_note_index(step)
    return NOTE_ORDER[(idx - 1) % 7]


def is_whole_tone_up(step: str) -> bool:
    return step.upper() not in NATURAL_SEMITONE_UP


def is_whole_tone_down(step: str) -> bool:
    return step.upper() not in NATURAL_SEMITONE_DOWN


def get_key_signature_accidentals(fifths: int) -> dict:
    accidentals = {}
    if fifths > 0:
        for i in range(fifths):
            accidentals[SHARP_ORDER[i]] = 'sharp'
    elif fifths < 0:
        for i in range(abs(fifths)):
            accidentals[FLAT_ORDER[i]] = 'flat'
    return accidentals


def analyze_note(step: str, octave: int, alter: float, key_fifths: int) -> dict:
    """
    分析音符，返回处理方案。

    返回 dict:
        step: 音名
        octave: 八度
        color: 颜色
        action: 'keep'（保持原音符标色）或 'replace'（替换为实际音高）
        alter: 替换后的 alter 值（仅 action='replace' 时有效）
    """
    step = step.upper()
    alter = int(alter)
    result = {'step': step, 'octave': octave, 'color': COLOR_BLACK, 'action': 'keep'}

    if alter == 0:
        return result

    # 重升 × (alter >= 2)：与普通升号相同逻辑
    if alter >= 2:
        if is_whole_tone_up(step):
            result['color'] = COLOR_RED
            result['action'] = 'keep'
        else:
            new_step = get_note_above(step)
            new_octave = octave + (1 if step == 'B' else 0)
            result['step'] = new_step
            result['octave'] = new_octave
            result['alter'] = 1
            result['color'] = COLOR_BLACK
            result['action'] = 'replace'
        return result

    # 重降 ♭♭ (alter <= -2)：与普通降号相同逻辑
    if alter <= -2:
        if is_whole_tone_down(step):
            result['color'] = COLOR_BLUE
            result['action'] = 'keep'
        else:
            new_step = get_note_below(step)
            new_octave = octave - (1 if step == 'C' else 0)
            result['step'] = new_step
            result['octave'] = new_octave
            result['alter'] = -1
            result['color'] = COLOR_BLACK
            result['action'] = 'replace'
        return result

    # 升号 ♯ (alter == 1)
    if alter == 1:
        if is_whole_tone_up(step):
            result['color'] = COLOR_RED
            result['action'] = 'keep'
        else:
            new_step = get_note_above(step)
            new_octave = octave + (1 if step == 'B' else 0)
            result['step'] = new_step
            result['octave'] = new_octave
            result['color'] = COLOR_BLACK
            result['action'] = 'replace'
        return result

    # 降号 ♭ (alter == -1)
    if alter == -1:
        if is_whole_tone_down(step):
            result['color'] = COLOR_BLUE
            result['action'] = 'keep'
        else:
            new_step = get_note_below(step)
            new_octave = octave - (1 if step == 'C' else 0)
            result['step'] = new_step
            result['octave'] = new_octave
            result['color'] = COLOR_BLACK
            result['action'] = 'replace'
        return result

    return result


def get_key_signature_note_alter(step: str, key_fifths: int) -> int:
    key_acc = get_key_signature_accidentals(key_fifths)
    acc_type = key_acc.get(step.upper())
    if acc_type == 'sharp':
        return 1
    elif acc_type == 'flat':
        return -1
    return 0
```

**颜色规则核心逻辑**：
- 升号音（♯、×）：如果该音上行是全音（E→F、B→C 除外），标品红；如果是半音（E→F、B→C），替换为实际音高（黑色）
- 降号音（♭、♭♭）：如果该音下行是全音（F→E、C→B 除外），标蓝色；如果是半音，替换为实际音高（黑色）
- 重升 × 和重降 ♭♭ 与普通升降号相同逻辑，保持原貌

---

## 文件 3：`musicxml_processor.py`

```python
"""
MusicXML 处理器
解析 MusicXML，提取调号、跟踪临时变音、注入颜色属性
"""

from lxml import etree
from copy import deepcopy
from color_engine import (
    analyze_note, get_key_signature_note_alter,
    COLOR_RED, COLOR_BLUE, COLOR_BLACK
)

NS = None


def _get_children(element, tag):
    if NS:
        return element.findall(f'{{{NS}}}{tag}')
    return element.findall(tag)


def _get_child(element, tag):
    if NS:
        return element.find(f'{{{NS}}}{tag}')
    return element.find(tag)


def _set_child_text(parent, tag, text):
    child = _get_child(parent, tag)
    if child is None:
        child = etree.SubElement(parent, tag)
    child.text = str(text)
    return child


def process_musicxml(xml_string: str) -> str:
    try:
        root = etree.fromstring(xml_string.encode('utf-8'))
    except Exception:
        return xml_string

    global NS
    tag = root.tag
    if '}' in tag:
        NS = tag.split('}')[0].strip('{')

    parts = _get_children(root, 'part') if NS is None else root.findall(f'{{{NS}}}part')
    if not parts:
        return xml_string

    key_fifths = _get_key_fifths(root)

    for part in parts:
        _process_part(part, key_fifths)

    return etree.tostring(root, encoding='unicode')


def _get_key_fifths(root) -> int:
    attrs = root.findall('.//{*}attributes') if NS else root.findall('.//attributes')
    if attrs:
        key = _get_child(attrs[0], 'key')
        if key is not None:
            fifths_el = _get_child(key, 'fifths')
            if fifths_el is not None and fifths_el.text:
                return int(fifths_el.text)
    return 0


def _process_part(part, key_fifths: int):
    measures = _get_children(part, 'measure')
    for measure in measures:
        key_fifths = _process_measure(measure, key_fifths)


def _process_measure(measure, key_fifths: int) -> int:
    """处理一个小节，返回更新后的调号 fifths 值"""
    current_accidentals = {}

    attributes = _get_child(measure, 'attributes')
    if attributes is not None:
        key = _get_child(attributes, 'key')
        if key is not None:
            fifths_el = _get_child(key, 'fifths')
            if fifths_el is not None and fifths_el.text:
                key_fifths = int(fifths_el.text)

    for note in _get_children(measure, 'note'):
        pitch = _get_child(note, 'pitch')
        if pitch is None:
            continue

        step_el = _get_child(pitch, 'step')
        octave_el = _get_child(pitch, 'octave')
        if step_el is None or octave_el is None:
            continue

        step = step_el.text
        octave = int(octave_el.text)

        alter_el = _get_child(pitch, 'alter')
        alter = float(alter_el.text) if alter_el is not None and alter_el.text else 0.0

        accidental = _get_child(note, 'accidental')
        has_explicit_acc = accidental is not None and accidental.text
        if has_explicit_acc:
            acc_text = accidental.text.strip()
            if acc_text == 'sharp':
                alter = 1
            elif acc_text == 'flat':
                alter = -1
            elif acc_text == 'natural':
                alter = 0
            elif acc_text == 'double-sharp':
                alter = 2
            elif acc_text == 'flat-flat':
                alter = -2

        # 获取声部号（多声部隔离）
        voice_el = _get_child(note, 'voice')
        voice = voice_el.text if voice_el is not None else '1'
        note_key = (step, octave, voice)

        if note_key in current_accidentals:
            saved_alter = current_accidentals[note_key]
            # 有显式变音记号时不从缓存取（还原号要覆盖之前的临时升降）
            if not has_explicit_acc and alter == 0:
                alter = saved_alter
        elif alter == 0:
            alter = get_key_signature_note_alter(step, key_fifths)

        # 始终更新缓存（包括还原号 alter=0，覆盖之前的临时变音）
        current_accidentals[note_key] = alter

        result = analyze_note(step, octave, alter, key_fifths)

        if result['action'] == 'replace':
            step_el.text = result['step']
            octave_el.text = str(result['octave'])
            if result.get('alter', 0) != 0:
                alter_el = _get_child(pitch, 'alter')
                if alter_el is None:
                    alter_el = etree.SubElement(pitch, 'alter')
                alter_el.text = str(result['alter'])
            else:
                for a in _get_children(pitch, 'alter'):
                    pitch.remove(a)
            if accidental is not None:
                note.remove(accidental)

        color = result['color']
        if color != COLOR_BLACK:
            note.set('color', color)

    return key_fifths
```

**处理逻辑**：
1. 解析调号（key/fifths）
2. 遍历每个 measure，跟踪临时变音（按声部隔离）
3. `note_key` 使用 `(step, octave, voice)` 元组，多声部互不干扰
4. 显式变音记号（含还原号）优先生效，不被缓存覆盖
5. 始终更新缓存（含 alter=0），还原号能正确清除后续同音颜色
6. `_process_measure` 返回更新后的 `key_fifths`，`_process_part` 逐小节捕获，确保跨小节调号变化传播

---

## 文件 4：`render_worker.py`

```python
"""
Verovio 渲染子进程
独立的 Python 脚本，接受 XML 文件路径，输出 SVG 文件路径
用法: python render_worker.py <input_xml> <output_svg> [--separate]
  --separate: 输出独立分页文件 (output_page1.svg, ...) 和 manifest JSON
"""
import sys
import os
import json
import re
import verovio
from lxml import etree

SVG_NS = 'http://www.w3.org/2000/svg'


def render_xml(input_path, output_path, separate=False):
    with open(input_path, 'r', encoding='utf-8') as f:
        xml = f.read()

    tk = verovio.toolkit()
    tk.setOptions({
        # 不设 pageWidth/pageHeight/scale，让 Verovio 从 MusicXML <defaults>/<print> 读取
        'breaks': 'encoded',        # 严格遵循原谱中的换行/换页标记
        'adjustPageWidth': False,   # 不自动调整页面宽度
        'footer': 'none',
        # 排版保真选项
        'justifyVertically': False,  # 不拉伸填满页面
        'noJustification': True,     # 不两端对齐小节，保留原始间距
        'systemDivider': 'none',     # 不用系统分隔符
    })
    tk.loadData(xml)

    page_count = tk.getPageCount()
    pages = [tk.renderToSVG(p) for p in range(1, page_count + 1)]

    if separate and page_count > 1:
        base_dir = os.path.dirname(output_path)
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        page_files = []
        for i, svg in enumerate(pages):
            page_path = os.path.join(base_dir, f'{base_name}_page{i+1}.svg')
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            page_files.append(page_path)

        manifest = {'page_count': page_count, 'files': page_files}
        manifest_path = os.path.join(base_dir, f'{base_name}_manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f)

        return page_count, manifest_path
    else:
        if page_count == 1:
            svg = pages[0]
        else:
            svg = _combine_pages(pages)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg)

        return len(svg), None


def _combine_pages(pages):
    """将多页 Verovio SVG 合并为纵向堆叠的单个 SVG"""
    roots = [etree.fromstring(p.encode('utf-8')) for p in pages]

    root = roots[0]
    inner_svg = root.find(f'{{{SVG_NS}}}svg')
    if inner_svg is None:
        return pages[0]

    page_heights = []
    for r in roots:
        inner = r.find(f'{{{SVG_NS}}}svg')
        if inner is not None:
            vb = inner.get('viewBox', '0 0 0 0')
            page_heights.append(float(vb.split()[3]))

    total_height = sum(page_heights)
    page_width = float(inner_svg.get('viewBox', '0 0 0 0').split()[2])

    inner_svg.set('viewBox', f'0 0 {page_width} {total_height}')

    merged_defs = root.find(f'{{{SVG_NS}}}defs')
    known_ids = set()
    if merged_defs is not None:
        for g in merged_defs.findall(f'{{{SVG_NS}}}g'):
            gid = g.get('id')
            if gid:
                known_ids.add(gid)
    for i, r in enumerate(roots):
        if i == 0:
            continue
        other_defs = r.find(f'{{{SVG_NS}}}defs')
        if other_defs is None:
            continue
        for g in other_defs.findall(f'{{{SVG_NS}}}g'):
            gid = g.get('id')
            if gid and gid not in known_ids:
                merged_defs.append(g)
                known_ids.add(gid)

    all_page_margins = []
    for r in roots:
        inner = r.find(f'{{{SVG_NS}}}svg')
        if inner is not None:
            all_page_margins.append(inner.findall(
                f'{{{SVG_NS}}}g[@class="page-margin"]'))

    for pm in inner_svg.findall(f'{{{SVG_NS}}}g[@class="page-margin"]'):
        inner_svg.remove(pm)

    y_offset = 0
    for i, pms in enumerate(all_page_margins):
        for pm in pms:
            transform = pm.get('transform', '')
            m = re.search(r'translate\(([^,]+),\s*([^)]+)\)', transform)
            if m:
                orig_x = float(m.group(1))
                orig_y = float(m.group(2)) + y_offset
                pm.set('transform', f'translate({orig_x}, {orig_y})')
            else:
                pm.set('transform', f'translate(0, {y_offset})')
            inner_svg.append(pm)
        y_offset += page_heights[i]

    scale = total_height / page_heights[0]
    outer_h = float(root.get('height', '0').replace('px', ''))
    root.set('height', f'{outer_h * scale}px')

    return etree.tostring(root, encoding='unicode')


if __name__ == '__main__':
    separate = '--separate' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 2:
        print("Usage: python render_worker.py <input_xml> <output_svg> [--separate]")
        sys.exit(1)

    result, manifest = render_xml(args[0], args[1], separate=separate)
    if manifest:
        print(f"OK:{manifest}")
    else:
        print(f"OK:{result}")
```

---

## 文件 5：`svg_postprocessor.py`

```python
"""
SVG 后处理器
将 Verovio 渲染的 SVG 中的颜色从 <g class="note"> 移到 <g class="notehead">，
确保符干保持黑色。
"""

from lxml import etree

SVG_NS = 'http://www.w3.org/2000/svg'

COLOR_RED = '#FF00FF'
COLOR_BLUE = '#0000FF'


def move_fill_to_notehead(svg_string: str) -> str:
    """
    将 fill 从 note 组移到 notehead 子组。
    这样符干和符尾保持黑色，只有符头变色。
    """
    root = etree.fromstring(svg_string.encode('utf-8'))

    note_groups = root.findall(f'.//{{{SVG_NS}}}g[@class="note"]')

    for note_group in note_groups:
        color = note_group.get('color')
        if color is None:
            fill_attr = note_group.get('fill')
            if fill_attr and fill_attr != '#000000' and fill_attr != 'black':
                color = fill_attr
        if color is None:
            continue

        notehead = note_group.find(f'.//{{{SVG_NS}}}g[@class="notehead"]')
        if notehead is not None:
            notehead.set('fill', color)
            notehead.set('color', color)
            paths = notehead.findall(f'.//{{{SVG_NS}}}path')
            for p in paths:
                p.set('fill', color)
        if note_group.get('fill'):
            del note_group.attrib['fill']

    return etree.tostring(root, encoding='unicode')
```

---

## 文件 6：`converter.py`

```python
"""
彩色五线谱转换器 — 主转换管线
MusicXML → 颜色规则引擎 → Verovio 渲染 → SVG 后处理
"""

import os
import base64
import subprocess
import tempfile
from musicxml_processor import process_musicxml
from svg_postprocessor import move_fill_to_notehead


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')
RENDER_WORKER = os.path.join(os.path.dirname(__file__), 'render_worker.py')


def set_colors(color_sharp: str = None):
    """设置升号颜色（降号颜色固定蓝色）"""
    import color_engine
    import svg_postprocessor
    if color_sharp:
        color_engine.COLOR_RED = color_sharp
        svg_postprocessor.COLOR_RED = color_sharp


def _render_via_subprocess_separate(xml_string: str) -> list:
    """通过子进程调用 Verovio 渲染为独立分页 SVG"""
    import sys, json
    tmp_xml = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8')
    tmp_svg = tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8')
    tmp_xml.write(xml_string)
    tmp_xml.close()
    tmp_svg.close()
    try:
        result = subprocess.run(
            [sys.executable, RENDER_WORKER, tmp_xml.name, tmp_svg.name, '--separate'],
            capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Verovio render failed (rc={result.returncode}): "
                               f"stdout={result.stdout}, stderr={result.stderr}")
        stdout = result.stdout.strip()
        if stdout.startswith('OK:') and '_manifest.json' in stdout:
            manifest_path = stdout[3:]
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            pages = []
            for pf in manifest['files']:
                with open(pf, 'r', encoding='utf-8') as f:
                    pages.append(f.read())
                try: os.unlink(pf)
                except OSError: pass
            try: os.unlink(manifest_path)
            except OSError: pass
            return pages
        else:
            with open(tmp_svg.name, 'r', encoding='utf-8') as f:
                return [f.read()]
    finally:
        try: os.unlink(tmp_xml.name)
        except OSError: pass
        try: os.unlink(tmp_svg.name)
        except OSError: pass


def convert_musicxml_to_colored_svg(xml_string: str, color_sharp: str = None) -> dict:
    """
    将 MusicXML 转换为彩色标注的 SVG（支持多页独立输出）

    返回: {'pages': [svg_str, ...], 'page_count': int}
    """
    set_colors(color_sharp)
    processed_xml = process_musicxml(xml_string)
    pages = _render_via_subprocess_separate(processed_xml)
    processed_pages = []
    for svg in pages:
        svg = _fix_svg_dimensions(svg)
        svg = move_fill_to_notehead(svg)
        processed_pages.append(svg)
    return {'pages': processed_pages, 'page_count': len(processed_pages)}


def _fix_svg_dimensions(svg_string: str) -> str:
    """从渲染结果中提取原始页面尺寸，保证 SVG 物理尺寸与排版一致"""
    from lxml import etree
    SVG_NS = 'http://www.w3.org/2000/svg'
    try:
        root = etree.fromstring(svg_string.encode('utf-8'))
    except Exception:
        return svg_string
    inner = root.find(f'{{{SVG_NS}}}svg')
    inner_vb = None
    if inner is not None:
        inner_vb = inner.get('viewBox')
    if inner_vb:
        parts = inner_vb.split()
        vb_w = int(float(parts[2]))
        vb_h = int(float(parts[3]))
    else:
        viewbox = root.get('viewBox')
        if viewbox:
            parts = viewbox.split()
            vb_w = int(float(parts[2]))
            vb_h = int(float(parts[3]))
        else:
            vb_w, vb_h = 21000, 29700
    root.set('viewBox', f'0 0 {vb_w} {vb_h}')
    root.set('width', f'{vb_w / 100:.0f}mm')
    root.set('height', f'{vb_h / 100:.0f}mm')
    return etree.tostring(root, encoding='unicode')


def svg_to_png_file(svg_string: str, output_path: str) -> bool:
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_string.encode('utf-8'), write_to=output_path)
        return True
    except Exception:
        return False


def get_svg_base64(svg_string: str) -> str:
    return base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')


def add_legend_to_svg(svg_string: str) -> str:
    """在 SVG 底部添加图例"""
    from lxml import etree
    SVG_NS = 'http://www.w3.org/2000/svg'
    try:
        root = etree.fromstring(svg_string.encode('utf-8'))
    except Exception:
        return svg_string
    outer_w_raw = root.get('width', '827')
    outer_h_raw = root.get('height', '1137')
    try:
        outer_w = float(outer_w_raw.replace('px', ''))
        outer_h = float(outer_h_raw.replace('px', ''))
    except ValueError:
        outer_w, outer_h = 827, 1137
    legend_w = 380
    legend_h = 140
    margin = 30
    legend_x = (outer_w - legend_w) / 2
    legend_y = outer_h + margin
    new_height = legend_y + legend_h + 20
    root.set('height', f'{new_height}px')
    vb = root.get('viewBox')
    if vb:
        vb_parts = vb.split()
        if len(vb_parts) == 4:
            vb_parts[3] = str(float(vb_parts[3]) * (new_height / outer_h))
            root.set('viewBox', ' '.join(vb_parts))
    legend_g = etree.SubElement(root, f'{{{SVG_NS}}}g', {
        'id': 'color-legend', 'font-family': 'sans-serif', 'font-size': '14',
        'transform': f'translate({legend_x:.0f}, {legend_y:.0f})'
    })
    title_el = etree.SubElement(legend_g, f'{{{SVG_NS}}}text',
        {'x': '15', 'y': '20', 'fill': '#333333', 'font-weight': 'bold', 'font-size': '16'})
    title_el.text = '彩色五线谱图例'
    items = [
        ('red_note', '#FF00FF', '粉色音符 = 升号音，弹该音右侧黑键'),
        ('blue_note', '#0000FF', '蓝色音符 = 降号音，弹该音左侧黑键'),
    ]
    for i, (item_id, color, text) in enumerate(items):
        item_y = 45 + i * 22
        etree.SubElement(legend_g, f'{{{SVG_NS}}}ellipse',
            {'cx': '10', 'cy': str(item_y - 5), 'rx': '7', 'ry': '5',
             'fill': color, 'stroke': '#999', 'stroke-width': '0.5'})
        text_el = etree.SubElement(legend_g, f'{{{SVG_NS}}}text',
            {'x': '26', 'y': str(item_y), 'fill': '#333333'})
        text_el.text = text
    legend_bg = etree.Element(f'{{{SVG_NS}}}rect', {
        'x': '0', 'y': '0', 'width': str(legend_w), 'height': str(legend_h),
        'fill': 'white', 'fill-opacity': '0.95', 'stroke': '#cccccc',
        'stroke-width': '1', 'rx': '5'})
    legend_g.insert(0, legend_bg)
    return etree.tostring(root, encoding='unicode')
```

---

## 文件 7：`app.py`

```python
"""
彩色五线谱转换器 — Web 服务
Flask 后端，提供文件上传和转换 API
"""

import os
import uuid
import io
import zipfile
import base64
from flask import Flask, request, render_template, jsonify, send_file
from converter import (
    convert_musicxml_to_colored_svg,
    get_svg_base64,
    svg_to_png_file,
)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'outputs')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': '彩色五线谱转换器'})


@app.route('/api/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({'error': '未找到上传文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    allowed_extensions = {'.xml', '.musicxml', '.mxl'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({
            'error': f'不支持的文件格式: {ext}，请上传 MusicXML 文件 (.xml / .musicxml / .mxl)'
        }), 400
    try:
        raw_bytes = file.read()
        # .mxl 解压
        if ext == '.mxl':
            import zipfile, io
            from lxml import etree
            try:
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                    container = zf.read('META-INF/container.xml').decode('utf-8')
                    container_root = etree.fromstring(container.encode('utf-8'))
                    rootfile = container_root.find(
                        './/{urn:oasis:names:tc:opendocument:xmlns:container}rootfile'
                    )
                    if rootfile is not None:
                        full_path = rootfile.get('full-path')
                        xml_string = zf.read(full_path).decode('utf-8')
                    else:
                        xml_string = None
                        for name in zf.namelist():
                            if name.endswith('.xml') and 'META-INF' not in name:
                                xml_string = zf.read(name).decode('utf-8')
                                break
                        if xml_string is None:
                            return jsonify({'error': '无法在 .mxl 文件中找到 MusicXML 内容'}), 400
            except Exception as e:
                return jsonify({'error': f'.mxl 文件解压失败: {str(e)}'}), 400
        else:
            xml_string = raw_bytes.decode('utf-8')

        task_id = str(uuid.uuid4())[:8]
        color_sharp = request.form.get('color_sharp') or None

        result = convert_musicxml_to_colored_svg(xml_string, color_sharp=color_sharp)
        pages = result['pages']
        page_count = result['page_count']

        svg_b64_list = []
        for i, svg_string in enumerate(pages):
            if page_count > 1:
                svg_path = os.path.join(OUTPUT_DIR, f'{task_id}_page{i+1}.svg')
            else:
                svg_path = os.path.join(OUTPUT_DIR, f'{task_id}.svg')
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_string)
            svg_b64_list.append(get_svg_base64(svg_string))

        return jsonify({
            'success': True,
            'task_id': task_id,
            'page_count': page_count,
            'svg_base64_list': svg_b64_list,
            'downloads': [
                f'/api/download/{task_id}_page{i+1}.svg' if page_count > 1
                else f'/api/download/{task_id}.svg'
                for i in range(page_count)
            ],
            'download_all': f'/api/download-all/{task_id}',
        })
    except UnicodeDecodeError:
        return jsonify({'error': '文件编码错误，请确认上传的是有效的 MusicXML 文件'}), 400
    except Exception as e:
        return jsonify({'error': f'转换失败: {str(e)}'}), 500


@app.route('/api/download-all/<task_id>')
def download_all(task_id):
    """批量下载所有分页（ZIP 打包）"""
    import glob as _glob
    pattern = os.path.join(OUTPUT_DIR, f'{task_id}*.svg')
    files = sorted(_glob.glob(pattern))
    if not files:
        return jsonify({'error': '文件未找到'}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.basename(f))
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'colored_score_{task_id}_svg.zip')


@app.route('/api/download/<filename>')
def download(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': '文件未找到'}), 404
    mimetype = 'image/svg+xml' if filename.endswith('.svg') else 'image/png'
    return send_file(file_path, mimetype=mimetype, as_attachment=True,
                     download_name=filename)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
```

---

## 文件 8：`templates/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>彩色五线谱转换器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: #f5f3f0;
            color: #333;
            min-height: 100vh;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }
        header {
            text-align: center;
            padding: 30px 0 20px;
            border-bottom: 2px solid #e0dcd5;
            margin-bottom: 30px;
        }
        header h1 { font-size: 28px; font-weight: 700; color: #2c2416; margin-bottom: 8px; }
        header p { color: #8c8478; font-size: 14px; }
        .upload-section {
            background: #fff;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }
        .upload-area {
            border: 2px dashed #d0cbc3;
            border-radius: 10px;
            padding: 50px 30px;
            cursor: pointer;
            transition: all 0.2s;
            background: #faf9f7;
        }
        .upload-area:hover { border-color: #b8a894; background: #f5f2ed; }
        .upload-area.dragover { border-color: #8b7355; background: #efe9e0; }
        .upload-icon { font-size: 48px; margin-bottom: 10px; }
        .upload-text { color: #6b6358; font-size: 15px; }
        .upload-hint { color: #a0988c; font-size: 12px; margin-top: 6px; }
        #file-input { display: none; }
        .btn {
            display: inline-block;
            padding: 10px 28px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }
        .btn-primary { background: #8b7355; color: #fff; }
        .btn-primary:hover { background: #6b5a43; }
        .btn-primary:disabled { background: #c5bcb0; cursor: not-allowed; }
        .btn-outline { background: #fff; color: #8b7355; border: 1px solid #8b7355; }
        .btn-outline:hover { background: #f5f2ed; }
        .result-section {
            display: none;
            margin-top: 30px;
            background: #fff;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }
        .result-title { font-size: 16px; font-weight: 600; color: #2c2416; }
        .download-btns { display: flex; gap: 8px; }
        .svg-preview {
            width: 100%;
            overflow-x: auto;
            border: 1px solid #e8e4de;
            border-radius: 8px;
            background: #fff;
            padding: 10px;
        }
        .svg-preview img, .svg-preview embed { max-width: 100%; height: auto; }
        .error-msg {
            background: #fef2f2;
            color: #991b1b;
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 16px;
            font-size: 14px;
            display: none;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            width: 32px; height: 32px;
            border: 3px solid #e8e4de;
            border-top-color: #8b7355;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .info-card {
            background: #faf9f7;
            border: 1px solid #e8e4de;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        .info-card h3 { font-size: 14px; color: #6b6358; margin-bottom: 10px; }
        .info-card ul { padding-left: 18px; color: #8c8478; font-size: 13px; line-height: 1.8; }
        .color-settings {
            background: #fff;
            border-radius: 12px;
            padding: 24px 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }
        .color-row {
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }
        .color-label {
            font-size: 14px;
            font-weight: 600;
            color: #2c2416;
            min-width: 70px;
        }
        .color-presets { display: flex; gap: 8px; flex-wrap: wrap; }
        .color-preset {
            width: 32px; height: 32px;
            border-radius: 6px;
            border: 2px solid #d0cbc3;
            cursor: pointer;
            transition: all 0.15s;
        }
        .color-preset:hover { transform: scale(1.15); }
        .color-preset.active {
            border-color: #333;
            box-shadow: 0 0 0 2px #fff, 0 0 0 4px #333;
        }
        .color-custom-wrap { display: flex; align-items: center; gap: 4px; }
        .color-custom-input {
            width: 32px; height: 32px;
            border: 2px solid #d0cbc3;
            border-radius: 6px;
            cursor: pointer;
            padding: 1px;
        }
        .color-hex-input {
            width: 80px;
            padding: 5px 8px;
            border: 1px solid #d0cbc3;
            border-radius: 4px;
            font-size: 13px;
            font-family: monospace;
            text-align: center;
        }
        .color-preview {
            display: inline-block;
            width: 14px; height: 14px;
            border-radius: 3px;
            vertical-align: middle;
            margin-right: 4px;
            border: 1px solid #ccc;
        }
        @media print {
            @page { margin: 0; }
            body { background: white; }
            .container { max-width: none; padding: 0; }
            header, .color-settings, .upload-section, .info-card,
            .result-header, .download-btns, #page-nav { display: none !important; }
            .svg-preview { border: none !important; padding: 0 !important; }
            .svg-preview img { width: 100%; page-break-after: always; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>彩色五线谱转换器</h1>
            <p>上传 MusicXML 乐谱，自动标注升降音颜色，让演奏更轻松</p>
        </header>

        <div class="color-settings">
            <div class="color-row">
                <span class="color-label">升号音颜色</span>
                <div class="color-presets" id="sharp-presets">
                    <div class="color-preset active" data-color="#FF00FF" style="background:#FF00FF" title="品红"></div>
                    <div class="color-preset" data-color="#9B4400" style="background:#9B4400" title="棕色"></div>
                    <div class="color-preset" data-color="#9B59B6" style="background:#9B59B6" title="紫色"></div>
                    <div class="color-preset" data-color="#E74C3C" style="background:#E74C3C" title="红色"></div>
                    <div class="color-preset" data-color="#FF8C00" style="background:#FF8C00" title="橙色"></div>
                </div>
                <div class="color-custom-wrap">
                    <input type="color" class="color-custom-input" id="sharp-custom" value="#FF00FF">
                    <input type="text" class="color-hex-input" id="sharp-hex" value="#FF00FF" maxlength="7">
                </div>
                <span style="color:#8c8478;font-size:13px;margin-left:8px;">降号音固定为蓝色</span>
            </div>
        </div>

        <div class="upload-section">
            <div class="upload-area" id="upload-area">
                <div class="upload-icon">&#x1F4C4;</div>
                <div class="upload-text">点击或拖拽 MusicXML 文件到此处</div>
                <div class="upload-hint">支持 .xml / .musicxml / .mxl 格式</div>
            </div>
            <input type="file" id="file-input" accept=".xml,.musicxml,.mxl">
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div style="color:#8c8478;">正在处理乐谱...</div>
        </div>

        <div class="error-msg" id="error-msg"></div>

        <div class="result-section" id="result-section">
            <div class="result-header">
                <span class="result-title">转换结果</span>
                <span id="page-indicator" style="display:none;color:#8c8478;font-size:14px;margin-left:12px;"></span>
                <div class="download-btns">
                    <button class="btn btn-primary" id="btn-download-png">下载当前页 PNG</button>
                    <button class="btn btn-outline" id="btn-download-svg">下载当前页 SVG</button>
                    <button class="btn btn-outline" id="btn-download-all">下载全部 SVG</button>
                    <button class="btn btn-outline" id="btn-reconvert">重新转换</button>
                </div>
            </div>
            <div class="svg-preview" id="svg-preview"></div>
            <div id="page-nav" style="display:none;text-align:center;margin-top:12px;gap:10px;justify-content:center;align-items:center;">
                <button class="btn btn-outline" id="btn-prev-page" style="padding:4px 16px;font-size:13px;">上一页</button>
                <span id="page-info" style="font-size:14px;color:#2c2416;"></span>
                <button class="btn btn-outline" id="btn-next-page" style="padding:4px 16px;font-size:13px;">下一页</button>
            </div>
        </div>

        <div class="info-card">
            <h3>使用说明</h3>
            <ul>
                <li>上传 MusicXML 格式的乐谱文件（.xml / .musicxml / .mxl）</li>
                <li><span class="color-preview" style="background:#FF00FF"></span>升号音 = 弹该音右侧黑键（颜色可自定义）</li>
                <li><span class="color-preview" style="background:#0000FF"></span>降号音 = 弹该音左侧黑键（固定蓝色）</li>
                <li>支持全部谱号（高音、低音、中音、次中音）和多声部</li>
                <li>多页乐谱按原谱分页显示和导出</li>
            </ul>
        </div>
    </div>

    <script>
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const loading = document.getElementById('loading');
        const errorMsg = document.getElementById('error-msg');
        const resultSection = document.getElementById('result-section');
        const svgPreview = document.getElementById('svg-preview');
        const btnDownloadSvg = document.getElementById('btn-download-svg');
        const btnDownloadPng = document.getElementById('btn-download-png');
        const btnDownloadAll = document.getElementById('btn-download-all');
        const btnReconvert = document.getElementById('btn-reconvert');

        let currentColorSharp = '#FF00FF';
        let currentPage = 0;
        let pageSvgList = [];
        let downloadLinks = [];
        let currentTaskId = '';
        let downloadAllUrl = '';
        let lastFile = null;

        function setupColorPicker(presetsId, customId, hexId) {
            const presets = document.getElementById(presetsId);
            const custom = document.getElementById(customId);
            const hex = document.getElementById(hexId);
            function selectColor(color) {
                presets.querySelectorAll('.color-preset').forEach(p => {
                    p.classList.toggle('active', p.dataset.color.toUpperCase() === color.toUpperCase());
                });
                custom.value = color;
                hex.value = color;
                currentColorSharp = color;
            }
            presets.addEventListener('click', (e) => {
                const preset = e.target.closest('.color-preset');
                if (!preset) return;
                selectColor(preset.dataset.color);
            });
            custom.addEventListener('input', () => { const color = custom.value; hex.value = color; selectColor(color); });
            hex.addEventListener('change', () => {
                let val = hex.value.trim();
                if (!val.startsWith('#')) val = '#' + val;
                if (/^#[0-9A-Fa-f]{6}$/.test(val)) { selectColor(val.toUpperCase()); }
                else { hex.value = custom.value; }
            });
        }
        setupColorPicker('sharp-presets', 'sharp-custom', 'sharp-hex');

        document.getElementById('btn-prev-page').addEventListener('click', () => { if (currentPage > 0) showPage(currentPage - 1); });
        document.getElementById('btn-next-page').addEventListener('click', () => { if (currentPage < pageSvgList.length - 1) showPage(currentPage + 1); });

        btnReconvert.addEventListener('click', () => { if (!lastFile) { alert('请先上传乐谱文件'); return; } doConvert(lastFile); });

        uploadArea.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFile);

        uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
        uploadArea.addEventListener('dragleave', () => { uploadArea.classList.remove('dragover'); });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) { fileInput.files = files; handleFile(); }
        });

        function handleFile() {
            const file = fileInput.files[0];
            if (!file) return;
            lastFile = file;
            doConvert(file);
        }

        function doConvert(file) {
            errorMsg.style.display = 'none';
            resultSection.style.display = 'none';
            loading.style.display = 'block';
            const formData = new FormData();
            formData.append('file', file);
            formData.append('color_sharp', currentColorSharp);
            fetch('/api/convert', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.error) { showError(data.error); return; }
                showResult(data);
            })
            .catch(err => { loading.style.display = 'none'; showError('网络错误: ' + err.message); });
        }

        function showResult(data) {
            pageSvgList = data.svg_base64_list;
            downloadLinks = data.downloads;
            currentTaskId = data.task_id;
            downloadAllUrl = data.download_all;
            currentPage = 0;
            const pageCount = data.page_count;
            const pageIndicator = document.getElementById('page-indicator');
            const pageNav = document.getElementById('page-nav');
            const pageInfo = document.getElementById('page-info');
            if (pageCount > 1) {
                pageIndicator.style.display = 'inline';
                pageIndicator.textContent = '共 ' + pageCount + ' 页';
                pageNav.style.display = 'flex';
                pageInfo.textContent = (currentPage + 1) + ' / ' + pageCount;
            } else {
                pageIndicator.style.display = 'none';
                pageNav.style.display = 'none';
            }
            showPage(0);
            resultSection.style.display = 'block';

            btnDownloadPng.onclick = function() {
                const b64 = pageSvgList[currentPage];
                if (!b64) return;
                const svgDataUrl = 'data:image/svg+xml;base64,' + b64;
                const svgImg = new Image();
                svgImg.onload = function() {
                    var c = document.createElement('canvas');
                    c.width = Math.max(svgImg.naturalWidth || svgImg.width || 800, 100);
                    c.height = Math.max(svgImg.naturalHeight || svgImg.height || 600, 100);
                    var cx = c.getContext('2d');
                    cx.fillStyle = '#ffffff';
                    cx.fillRect(0, 0, c.width, c.height);
                    cx.drawImage(svgImg, 0, 0, c.width, c.height);
                    c.toBlob(function(blob) {
                        var url = URL.createObjectURL(blob);
                        var a = document.createElement('a');
                        a.href = url;
                        var pn = pageSvgList.length > 1 ? '_page' + (currentPage + 1) : '';
                        a.download = 'colored_score' + pn + '.png';
                        a.click();
                        setTimeout(function() { URL.revokeObjectURL(url); }, 100);
                    }, 'image/png');
                };
                svgImg.onerror = function() { alert('SVG 转换失败，请尝试下载 SVG 格式'); };
                svgImg.src = svgDataUrl;
            };

            btnDownloadSvg.onclick = function() {
                var a = document.createElement('a');
                a.href = downloadLinks[currentPage];
                var pn = pageSvgList.length > 1 ? '_page' + (currentPage + 1) : '';
                a.download = 'colored_score' + pn + '.svg';
                a.click();
            };

            btnDownloadAll.onclick = function() {
                var a = document.createElement('a');
                a.href = downloadAllUrl;
                a.download = 'colored_score_' + currentTaskId + '_svg.zip';
                a.click();
            };
        }

        function showPage(idx) {
            currentPage = idx;
            var b64 = pageSvgList[idx];
            var svgUrl = 'data:image/svg+xml;base64,' + b64;
            svgPreview.innerHTML = '<img src="' + svgUrl + '" alt="彩色五线谱" style="max-width:100%;height:auto;border:1px solid #e8e4de;">';
            var pageInfo = document.getElementById('page-info');
            if (pageSvgList.length > 1) { pageInfo.textContent = (idx + 1) + ' / ' + pageSvgList.length; }
        }

        function showError(msg) { errorMsg.textContent = msg; errorMsg.style.display = 'block'; }
    </script>
</body>
</html>
```

---

## 文件 9：`Dockerfile`

```dockerfile
FROM python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads outputs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 10000

CMD ["sh", "-c", "cd /app && gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120 --preload"]
```

---

## 文件 10：`fly.toml`

```toml
app = "color-sheet-music"
primary_region = "hkg"

[build]

[http_service]
  internal_port = 10000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

---

## 文件 11：`.gitignore`

```
__pycache__/
*.pyc
*.pyo
venv/
.env
*.log
*.egg-info/
dist/
build/
```

---

## 文件 12：`.dockerignore`

```
__pycache__/
*.pyc
*.pyo
outputs/
uploads/
*.mxl
*.xml
*.musicxml
*.svg
*.png
*.zip
.git/
test_*.py
check_*.py
debug_*.py
compare_*.py
*.md
彩色五线谱转换器_Agent.md
```

---

## 部署步骤

```bash
# 1. 安装依赖
cd color_sheet_music
pip install -r requirements.txt

# 2. 启动服务
python app.py
# 访问 http://127.0.0.1:5000

# 3. Docker 部署
docker build -t color-sheet-music .
docker run -p 5000:10000 color-sheet-music

# 4. Fly.io 部署
fly deploy
```

---

## 关键设计决策

1. **降号颜色固定蓝色**：`COLOR_BLUE = '#0000FF'`，前端不提供降号颜色选择
2. **升号颜色可自定义**：`COLOR_RED = '#FF00FF'`（默认品红），前端提供 5 个预设 + 自定义
3. **调号音仅颜色提示**：删除 accidental 和 alter 元素，避免重复显示变音符号
4. **临时变音双提示**：颜色 + 保留 accidental 符号
5. **重升/重降保持原貌**：与普通升降号相同逻辑（全音标色保留，半音替换）
6. **子进程渲染**：Verovio 在独立 Python 进程中运行，避免 Flask 环境中的渲染异常
7. **原谱布局保真**：Verovio 不设 pageWidth/pageHeight/scale，从 MusicXML 读取原始布局
8. **分页独立输出**：每页独立 SVG 文件，前端支持分页预览和单独/批量下载
9. **SVG 物理尺寸**：从内层 viewBox 提取，按 1 Verovio unit ≈ 0.01 mm 换算
10. **PNG 下载**：前端 Canvas 转换，无需后端 Cairo

## Verovio 渲染选项

| 选项 | 值 | 语义 |
|------|------|------|
| `breaks` | `'encoded'` | 严格遵循原谱换行/换页标记 |
| `adjustPageWidth` | `False` | 不自动调整页面宽度 |
| `justifyVertically` | `False` | 不拉伸填满页面 |
| `noJustification` | `True` | 不两端对齐小节，保留原始音符间距 |
| `systemDivider` | `'none'` | 不用系统分隔符 |
| `footer` | `'none'` | 不显示页脚 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端页面 |
| GET | `/api/health` | 健康检查 |
| POST | `/api/convert` | MusicXML → 彩色 SVG |
| GET | `/api/download/<filename>` | 单页下载 |
| GET | `/api/download-all/<task_id>` | 全部页面 ZIP 下载 |

## 转换 API 响应格式

```json
{
  "success": true,
  "task_id": "a1b2c3d4",
  "page_count": 2,
  "svg_base64_list": ["...", "..."],
  "downloads": ["/api/download/a1b2c3d4_page1.svg", "..."],
  "download_all": "/api/download-all/a1b2c3d4"
}
```

## 颜色规则速查

| 音名 | alter | 全音/半音 | 动作 | 颜色 |
|------|-------|-----------|------|------|
| C→D | +1 | 全音 | keep | 品红 |
| E→F | +1 | 半音 | replace→F | 黑色 |
| B→C | +1 | 半音 | replace→C | 黑色 |
| D→C | -1 | 全音 | keep | 蓝色 |
| F→E | -1 | 半音 | replace→E | 黑色 |
| C→B | -1 | 半音 | replace→B | 黑色 |