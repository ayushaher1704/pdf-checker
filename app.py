from flask import Flask, request, jsonify
from flask import render_template
from flask_cors import CORS
import fitz

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/check-pdf', methods=['POST'])
def check_pdf():

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files allowed'}), 400

    pdf_bytes = file.read()
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')

    page      = doc[0]
    num_pages = doc.page_count

    width_mm  = round(page.rect.width  * 0.3528, 1)
    height_mm = round(page.rect.height * 0.3528, 1)

    if abs(width_mm - 210) <= 2 and abs(height_mm - 297) <= 2:
        page_size = 'A4'
    elif abs(width_mm - 216) <= 2 and abs(height_mm - 279) <= 2:
        page_size = 'US Letter'
    else:
        page_size = 'Custom'

    file_size_kb = round(len(pdf_bytes) / 1024, 1)

    doc.close()

    return jsonify({
        'filename'    : file.filename,
        'pages'       : num_pages,
        'file_size_kb': file_size_kb,
        'page_size'   : page_size,
        'width_mm'    : width_mm,
        'height_mm'   : height_mm,
        'status'      : 'ok'
    })


if __name__ == '__main__':
    app.run(debug=True)