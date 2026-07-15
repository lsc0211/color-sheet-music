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
        _process_measure(measure, key_fifths)


def _process_measure(measure, key_fifths: int):
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
        if accidental is not None and accidental.text:
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

        note_key = f"{step}{octave}"
        if note_key in current_accidentals:
            saved_alter = current_accidentals[note_key]
            if alter == 0:
                alter = saved_alter
        elif alter == 0:
            alter = get_key_signature_note_alter(step, key_fifths)

        if alter != 0:
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