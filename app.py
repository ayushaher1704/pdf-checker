from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import fitz

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024


def pt_to_mm(pt):
    return round(pt * 0.3528, 1)


def check_allowed_fonts(doc, allowed_fonts):

    if not allowed_fonts:
        return {
            'name': 'Allowed fonts',
            'passed': True,
            'message': 'No font restrictions selected',
            'detail': 'No allowed font list provided'
        }

    wrong_pages = []
    fonts_found = set()
    unexpected_fonts = set()

    allowed_norm = [
        font.lower().replace(' ', '')
        for font in allowed_fonts
    ]

    for page_num, page in enumerate(doc):

        for block in page.get_text('dict')['blocks']:

            if block['type'] != 0:
                continue

            for line in block['lines']:

                for span in line['spans']:

                    base = span['font'].split('-')[0].split(',')[0].strip()

                    # Normalize display names
                    display_font = base

                    if "timesnewroman" in base.lower():
                        display_font = "Times New Roman"

                    elif "arial" in base.lower():
                        display_font = "Arial"

                    elif "calibri" in base.lower():
                        display_font = "Calibri"

                    elif "georgia" in base.lower():
                        display_font = "Georgia"

                    fonts_found.add(display_font)

                    actual = display_font.lower().replace(' ', '')

                    allowed = any(
                        font in actual
                        for font in allowed_norm
                    )

                    if not allowed:

                        unexpected_fonts.add(display_font)

                        if page_num + 1 not in wrong_pages:
                            wrong_pages.append(page_num + 1)

    passed = len(unexpected_fonts) == 0

    return {
        'name': 'Allowed fonts',
        'passed': passed,
        'message':
            'All fonts are allowed'
            if passed
            else 'Unexpected fonts: ' +
                 ', '.join(sorted(unexpected_fonts)),
        'detail':
            f'Allowed fonts: {", ".join(allowed_fonts)}\n'
            f'Fonts found: {", ".join(sorted(fonts_found))}\n'
            f'Pages affected: {wrong_pages[:10]}'
    }


def check_font_name(doc, expected_font):
    wrong_pages = []
    fonts_found = set()

    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    base = span['font'].split('-')[0].split(',')[0].strip()
                    fonts_found.add(base)
                    expected = expected_font.lower().replace(" ", "")
                    actual = base.lower().replace(" ", "")

                    if expected not in actual:
                        if page_num + 1 not in wrong_pages:
                            wrong_pages.append(page_num + 1)

    passed = len(wrong_pages) == 0
    return {
        'name'   : f'Font — {expected_font}',
        'passed' : passed,
        'message': f'All text uses {expected_font}' if passed else
                   f'Wrong font on pages {wrong_pages[:5]}',
        'detail' : 'Fonts found: ' + ', '.join(sorted(fonts_found))
    }


def check_chapter_title(doc):
    found = []
    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    size = span['size']
                    bold = 'bold' in span['font'].lower() or span['flags'] & 2**4
                    if size >= 15.5 and bold:
                        found.append({
                            'page': page_num + 1,
                            'size': round(size, 1),
                            'text': span['text'][:40]
                        })

    passed = len(found) > 0
    detail = '; '.join([f"p{f['page']}: \"{f['text']}\" ({f['size']}pt)" for f in found[:3]])
    return {
        'name'   : 'Chapter title (16pt bold)',
        'passed' : passed,
        'message': f'{len(found)} chapter title(s) found' if passed else
                   'No 16pt bold text found',
        'detail' : detail if detail else 'None found'
    }


def check_section_heading(doc):
    found = []
    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    size = span['size']
                    bold = 'bold' in span['font'].lower() or span['flags'] & 2**4
                    if 13.5 <= size < 15.5 and bold:
                        found.append({
                            'page': page_num + 1,
                            'size': round(size, 1),
                            'text': span['text'][:40]
                        })

    passed = len(found) > 0
    detail = '; '.join([f"p{f['page']}: \"{f['text']}\" ({f['size']}pt)" for f in found[:3]])
    return {
        'name'   : 'Section heading (14pt bold)',
        'passed' : passed,
        'message': f'{len(found)} section heading(s) found' if passed else
                   'No 14pt bold text found',
        'detail' : detail if detail else 'None found'
    }


def check_subsection_heading(doc):
    found = []
    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    size = span['size']
                    bold = 'bold' in span['font'].lower() or span['flags'] & 2**4
                    if 11.5 <= size < 13.5 and bold:
                        found.append({
                            'page': page_num + 1,
                            'size': round(size, 1),
                            'text': span['text'][:40]
                        })

    passed = len(found) > 0
    detail = '; '.join([f"p{f['page']}: \"{f['text']}\" ({f['size']}pt)" for f in found[:3]])
    return {
        'name'   : 'Sub-section heading (12pt bold)',
        'passed' : passed,
        'message': f'{len(found)} sub-section heading(s) found' if passed else
                   'No 12pt bold text found',
        'detail' : detail if detail else 'None found'
    }


def check_body_text(doc):
    violations = []
    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    size = span['size']
                    bold = 'bold' in span['font'].lower() or span['flags'] & 2**4
                    text = span['text'].strip()
                    if len(text) <= 2:
                        continue
                    if not bold and size < 11.5:
                        violations.append(f"p{page_num+1}: {round(size,1)}pt")

    passed = len(violations) == 0
    return {
        'name'   : 'Body text (12pt normal)',
        'passed' : passed,
        'message': 'All body text is 12pt or above' if passed else
                   f'{len(violations)} body text violation(s) found',
        'detail' : ', '.join(violations[:5]) if violations else 'No issues'
    }


def check_margins(doc, exp_top=25, exp_bottom=25, exp_left=25, exp_right=25):
    violations = []

    for page_num, page in enumerate(doc):
        blocks = page.get_text('dict')['blocks']
        text_blocks = []
        for b in blocks:
            if b['type'] != 0:
                continue
            text = ''.join(
                span['text']
                for line in b['lines']
                for span in line['spans']
            ).strip()
            if len(text) <= 3:
                continue
            text_blocks.append(b)

        if not text_blocks:
            continue

        left_x   = min(b['bbox'][0] for b in text_blocks)
        top_y    = min(b['bbox'][1] for b in text_blocks)
        right_x  = max(b['bbox'][2] for b in text_blocks)
        bottom_y = max(b['bbox'][3] for b in text_blocks)

        page_w = page.rect.width
        page_h = page.rect.height

        left_mm   = pt_to_mm(left_x)
        top_mm    = pt_to_mm(top_y)
        right_mm  = pt_to_mm(page_w - right_x)
        bottom_mm = pt_to_mm(page_h - bottom_y)

        page_v = []
        if left_mm   < exp_left:   page_v.append(f'Left:{left_mm}mm')
        if right_mm  < exp_right:  page_v.append(f'Right:{right_mm}mm')
        if top_mm    < exp_top:    page_v.append(f'Top:{top_mm}mm')
        if bottom_mm < exp_bottom: page_v.append(f'Bottom:{bottom_mm}mm')

        if page_v:
            violations.append(f'Page {page_num+1}: ' + ' | '.join(page_v))

    passed = len(violations) == 0
    return {
        'name'   : 'Margins',
        'passed' : passed,
        'message': 'All margins within limits' if passed else
                   f'{len(violations)} page(s) have margin violations',
        'detail' : '\n'.join(violations) if violations else 'No violations'
    }


def check_columns(doc, expected='single'):
    double_pages = []
    for page_num, page in enumerate(doc):
        blocks     = page.get_text('dict')['blocks']
        text_blocks = [b for b in blocks if b['type'] == 0]
        if len(text_blocks) < 4:
            continue
        page_w  = page.rect.width
        mid_x   = page_w / 2
        left_col  = [b for b in text_blocks if b['bbox'][2] < mid_x - 20]
        right_col = [b for b in text_blocks if b['bbox'][0] > mid_x + 20]
        if len(left_col) >= 2 and len(right_col) >= 2:
            double_pages.append(page_num + 1)

    is_double = len(double_pages) > 0
    if expected == 'single':
        passed  = not is_double
        message = 'Single column confirmed' if passed else \
                  f'Double column on pages {double_pages}'
    else:
        passed  = is_double
        message = 'Double column confirmed' if passed else \
                  'Single column detected — expected double'

    return {
        'name'   : 'Column layout',
        'passed' : passed,
        'message': message,
        'detail' : f'Expected: {expected} | Double pages: {double_pages if double_pages else "none"}'
    }


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/check-pdf', methods=['POST'])
def check_pdf():

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']


    # Read all checkbox values
    do_font      = request.form.get('check_font',      'true')  == 'true'
    do_times     = request.form.get('check_times',     'true')  == 'true'
    do_arial     = request.form.get('check_arial',     'false') == 'true'
    do_calibri   = request.form.get('check_calibri',   'false') == 'true'
    do_georgia   = request.form.get('check_georgia',   'false') == 'true'

    do_size      = request.form.get('check_font_size', 'true')  == 'true'
    do_size16    = request.form.get('check_size16',    'true')  == 'true'
    do_size14    = request.form.get('check_size14',    'true')  == 'true'
    do_size12b   = request.form.get('check_size12bold','true')  == 'true'
    do_size12    = request.form.get('check_size12',    'true')  == 'true'

    do_margin    = request.form.get('check_margin',    'true')  == 'true'
    exp_top      = float(request.form.get('top',       25))
    exp_bottom   = float(request.form.get('bottom',    25))
    exp_left     = float(request.form.get('left',      25))
    exp_right    = float(request.form.get('right',     25))

    do_col       = request.form.get('check_col',       'true')  == 'true'
    expected_col = request.form.get('columns',         'single')

    pdf_bytes = file.read()
    doc       = fitz.open(stream=pdf_bytes, filetype='pdf')

    page      = doc[0]
    num_pages = doc.page_count
    width_mm  = round(page.rect.width  * 0.3528, 1)
    height_mm = round(page.rect.height * 0.3528, 1)

    if abs(width_mm - 210) <= 2 and abs(height_mm - 297) <= 2:
        page_size = 'A4'
    elif abs(width_mm - 216) <= 2 and abs(height_mm - 279) <= 2:
        page_size = 'US Letter'
    else:
        page_size = f'Custom ({width_mm}×{height_mm}mm)'

    file_size_kb = round(len(pdf_bytes) / 1024, 1)

    checks = []

    # Font name checks
    if do_font:
        allowed_fonts = []

        if do_times:
            allowed_fonts.append("Times New Roman")

        if do_arial:
            allowed_fonts.append("Arial")

        if do_calibri:
            allowed_fonts.append("Calibri")

        if do_georgia:
            allowed_fonts.append("Georgia")

        checks.append(
            check_allowed_fonts(
                doc,
                allowed_fonts
            )
        )

    # Font size checks
    if do_size:

        if do_size16:
            checks.append(check_chapter_title(doc))

        if do_size14:
            checks.append(check_section_heading(doc))

        if do_size12b:
            checks.append(check_subsection_heading(doc))

        if do_size12:
            checks.append(check_body_text(doc))
    # Margin check
    if do_margin:
        checks.append(
            check_margins(
                doc,
                exp_top,
                exp_bottom,
                exp_left,
                exp_right
            )
        )

    # Column check
    # map expected_col ('single'/'double') to function parameter
    if do_col:
        checks.append(
            check_columns(
                doc,
                expected_col
            )
        )
    doc.close()

    passed_count = sum(1 for c in checks if c['passed'])

    return jsonify({
        'filename'     : file.filename,
        'pages'        : num_pages,
        'file_size_kb' : file_size_kb,
        'page_size'    : page_size,
        'total_checks' : len(checks),
        'passed_count' : passed_count,
        'failed_count' : len(checks) - passed_count,
        'checks'       : checks,
        'status'       : 'ok'
    })


if __name__ == '__main__':
    app.run(debug=True)