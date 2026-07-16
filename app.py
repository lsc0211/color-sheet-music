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


@app.route('/api/version')
def version():
    return jsonify({
        'version': '1.1',
        'commit': '02e9e23',
        'date': '2026-07-17',
        'changes': '修复还原记号颜色污染、多声部碰撞、跨小节调号传播；新增溢出检测双遍渲染'
    })


@app.route('/api/test_vrv')
def test_vrv():
    import verovio, os, sys
    info = {
        'cwd': os.getcwd(),
        'python': sys.executable,
        'verovio_file': verovio.__file__,
    }
    tk = verovio.toolkit()
    info['resource_path'] = tk.getResourcePath()
    tk.setOptions({
        'pageWidth': 2100, 'pageHeight': 2970, 'scale': 40,
        'adjustPageWidth': True, 'adjustPageHeight': True,
        'footer': 'none', 'header': 'none',
    })
    test_xml = '<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure></part></score-partwise>'
    tk.loadData(test_xml)
    svg = tk.renderToSVG()
    import re
    w = re.search(r'width="([^"]+)"', svg)
    info['svg_len'] = len(svg)
    info['width'] = w.group(1) if w else 'NONE'
    info['has_note'] = 'note' in svg.lower()
    return jsonify(info)


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
        svg_paths = []
        svg_b64_list = []
        for i, svg_string in enumerate(pages):
            if page_count > 1:
                svg_path = os.path.join(OUTPUT_DIR, f'{task_id}_page{i+1}.svg')
            else:
                svg_path = os.path.join(OUTPUT_DIR, f'{task_id}.svg')
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_string)
            svg_paths.append(svg_path)
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