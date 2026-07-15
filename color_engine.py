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
    step = step.upper()
    alter = int(alter)
    result = {'step': step, 'octave': octave, 'color': COLOR_BLACK, 'action': 'keep', 'mark': None}
    if alter == 0:
        return result
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