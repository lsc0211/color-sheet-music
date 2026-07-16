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

    # === 从 MusicXML <defaults> 解析原始页面尺寸 ===
    page_width, page_height = _parse_musicxml_page_size(xml)

    # === 第 1 遍：严格保真渲染 ===
    strict_opts = {
        'breaks': 'encoded',
        'adjustPageWidth': False,
        'footer': 'none',
        'justifyVertically': False,
        'noJustification': False,
        'systemDivider': 'none',
    }
    if page_width:
        strict_opts['pageWidth'] = page_width
    if page_height:
        strict_opts['pageHeight'] = page_height

    tk = verovio.toolkit()
    tk.setOptions(strict_opts)
    tk.loadData(xml)
    page_count = tk.getPageCount()
    pages = [tk.renderToSVG(p) for p in range(1, page_count + 1)]

    # === 溢出检测 ===
    overflow_pages = _detect_overflow_pages(pages)

    if overflow_pages:
        # === 第 2 遍：自适应渲染，确保完整显示 ===
        auto_opts = {
            'breaks': 'auto',
            'adjustPageWidth': True,
            'footer': 'none',
            'justifyVertically': False,
            'noJustification': False,
            'systemDivider': 'none',
        }
        if page_width:
            auto_opts['pageWidth'] = page_width
        if page_height:
            auto_opts['pageHeight'] = page_height

        tk2 = verovio.toolkit()
        tk2.setOptions(auto_opts)
        tk2.loadData(xml)
        page_count = tk2.getPageCount()
        pages = [tk2.renderToSVG(p) for p in range(1, page_count + 1)]

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


def _parse_musicxml_page_size(xml_string: str) -> tuple:
    """从 MusicXML <defaults> 解析页面尺寸，返回 (page_width, page_height) 或 (None, None)。
    值已转换为 Verovio 单位（1/10 mm）。"""
    try:
        root = etree.fromstring(xml_string.encode('utf-8'))
    except Exception:
        return None, None

    # 查找缩放比例
    scaling_mm = 7.0    # 默认：40 tenths = 7.0mm
    scaling_tenths = 40
    for scaling in root.iter('{*}scaling'):
        mm_el = scaling.find('{*}millimeters')
        th_el = scaling.find('{*}tenths')
        if mm_el is not None and mm_el.text:
            scaling_mm = float(mm_el.text)
        if th_el is not None and th_el.text:
            scaling_tenths = float(th_el.text)

    tenths_per_mm = scaling_tenths / scaling_mm  # ≈ 40/7.0 = 5.714

    pw, ph = None, None
    for page_layout in root.iter('{*}page-layout'):
        pw_el = page_layout.find('{*}page-width')
        ph_el = page_layout.find('{*}page-height')
        if pw_el is not None and pw_el.text:
            mm_val = float(pw_el.text) / tenths_per_mm
            pw = int(mm_val * 10)  # 转换为 Verovio 单位 (1/10 mm)
        if ph_el is not None and ph_el.text:
            mm_val = float(ph_el.text) / tenths_per_mm
            ph = int(mm_val * 10)

    return pw, ph


def _detect_overflow_pages(pages: list) -> bool:
    """检测是否有页面内容超出 viewBox 边界（被截断）。返回 True 表示存在溢出。"""
    for svg in pages:
        if _detect_single_page_overflow(svg):
            return True
    return False


def _detect_single_page_overflow(svg_string: str) -> bool:
    """检测单页 SVG 中是否有内容超出 viewBox 宽度（被截断）"""
    try:
        root = etree.fromstring(svg_string.encode('utf-8'))
    except Exception:
        return False

    inner = root.find(f'{{{SVG_NS}}}svg')
    if inner is None:
        return False

    vb = inner.get('viewBox')
    if not vb:
        return False
    vb_w = float(vb.split()[2])

    # 遍历所有 system → measure → staff 的谱线路径，找最右 x 坐标
    for system in inner.iter(f'{{{SVG_NS}}}g'):
        if system.get('class') != 'system':
            continue
        max_x = 0
        for path in system.iter(f'{{{SVG_NS}}}path'):
            d = path.get('d', '')
            # 提取路径中的所有 x 坐标（M x y L x y 格式的谱线）
            coords = re.findall(r'[ML]\s*([\d.]+)', d)
            for c in coords:
                max_x = max(max_x, float(c))
        # 也检查 measure 元素上的 x + width 属性
        for measure in system.iter(f'{{{SVG_NS}}}g'):
            if measure.get('class') != 'measure':
                continue
            m_x = measure.get('x')
            m_w = measure.get('width')
            if m_x is not None and m_w is not None:
                max_x = max(max_x, float(m_x) + float(m_w))
        if max_x > vb_w + 1:  # 1px 容差
            return True

    return False


def _combine_pages(pages):
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
            all_page_margins.append(inner.findall(f'{{{SVG_NS}}}g[@class="page-margin"]'))

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