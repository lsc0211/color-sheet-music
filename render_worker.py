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
        'breaks': 'encoded',
        'adjustPageWidth': False,
        'footer': 'none',
        'justifyVertically': False,
        'noJustification': True,
        'systemDivider': 'none',
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