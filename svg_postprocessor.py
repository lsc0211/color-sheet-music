"""
SVG 后处理器
在 Verovio 渲染的 SVG 上叠加 45° 斜线标记（重升/重降追溯标记）
"""

from lxml import etree

SVG_NS = 'http://www.w3.org/2000/svg'

COLOR_RED = '#FF00FF'
COLOR_BLUE = '#0000FF'


def move_fill_to_notehead(svg_string: str) -> str:
    root = etree.fromstring(svg_string.encode('utf-8'))

    note_groups = root.findall(f'.//{{{SVG_NS}}}g[@class="note"]')
    if not note_groups:
        all_g = root.findall(f'.//{{{SVG_NS}}}g')

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