"""
彩色五线谱转换器 — 主转换管线
MusicXML → 颜色规则引擎 → Verovio 渲染 → SVG → 斜线后处理 → PNG/JPG
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
    import color_engine
    import svg_postprocessor
    if color_sharp:
        color_engine.COLOR_RED = color_sharp
        svg_postprocessor.COLOR_RED = color_sharp


def _render_via_subprocess_separate(xml_string: str) -> list:
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
        ('red_mark', '#FF00FF', '粉色斜线 = 曾是重升音，已换算为实际音高'),
        ('blue_mark', '#0000FF', '蓝色斜线 = 曾是重降音，已换算为实际音高'),
    ]
    for i, (item_id, color, text) in enumerate(items):
        item_y = 45 + i * 22
        if 'note' in item_id:
            etree.SubElement(legend_g, f'{{{SVG_NS}}}ellipse',
                {'cx': '10', 'cy': str(item_y - 5), 'rx': '7', 'ry': '5',
                 'fill': color, 'stroke': '#999', 'stroke-width': '0.5'})
        else:
            etree.SubElement(legend_g, f'{{{SVG_NS}}}line',
                {'x1': '3', 'y1': str(item_y - 1), 'x2': '17', 'y2': str(item_y - 9),
                 'stroke': color, 'stroke-width': '1.5', 'stroke-linecap': 'round'})
        text_el = etree.SubElement(legend_g, f'{{{SVG_NS}}}text',
            {'x': '26', 'y': str(item_y), 'fill': '#333333'})
        text_el.text = text
    legend_bg = etree.Element(f'{{{SVG_NS}}}rect', {
        'x': '0', 'y': '0', 'width': str(legend_w), 'height': str(legend_h),
        'fill': 'white', 'fill-opacity': '0.95', 'stroke': '#cccccc',
        'stroke-width': '1', 'rx': '5'})
    legend_g.insert(0, legend_bg)
    return etree.tostring(root, encoding='unicode')