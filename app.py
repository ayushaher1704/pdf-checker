from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import fitz
app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024


def pt_to_mm(pt):
    return round(pt * 0.3528, 1)


def check_font_name(doc):
    fonts_found = set()
    pages_info  = {}

    for page_num, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                for span in line['spans']:
                    base = span['font'].split('-')[0].split(',')[0].strip()
                    fonts_found.add(base)
                    if base not in pages_info:
                        pages_info[base] = []
                    if page_num + 1 not in pages_info[base]:
                        pages_info[base].append(page_num + 1)

    detail = ' | '.join([
        f"{font}: p{pages}"
        for font, pages in pages_info.items()
    ])

    return {
        'name'   : 'Fonts detected',
        'passed' : True,
        'message': f'{len(fonts_found)} font(s) found: {", ".join(sorted(fonts_found))}',
        'detail' : detail
    }

# ── Check 2: Chapter title — 16pt bold ───────────────────────────────────────
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


# ── Check 3: Section heading — 14pt bold ─────────────────────────────────────
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


# ── Check 4: Sub-section — 12pt bold ─────────────────────────────────────────
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


# ── Check 5: Body text — 12pt normal ─────────────────────────────────────────
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


# ── Check 6: Margins ──────────────────────────────────────────────────────────
def check_margins(doc, exp_top=25, exp_bottom=25, exp_left=25, exp_right=25):
    violations = []
    all_ok     = True

    for page_num, page in enumerate(doc):
        blocks = page.get_text('dict')['blocks']

        # Collect only text blocks with meaningful content
        text_blocks = []
        for b in blocks:
            if b['type'] != 0:
                continue
            text = ''.join(
                span['text']
                for line in b['lines']
                for span in line['spans']
            ).strip()
            # Skip page numbers and tiny junk
            if len(text) <= 3:
                continue
            text_blocks.append(b)

        if not text_blocks:
            continue

        # Find bounding box of all content on this page
        left_x   = min(b['bbox'][0] for b in text_blocks)
        top_y    = min(b['bbox'][1] for b in text_blocks)
        right_x  = max(b['bbox'][2] for b in text_blocks)
        bottom_y = max(b['bbox'][3] for b in text_blocks)

        page_w = page.rect.width
        page_h = page.rect.height

        # Convert to mm
        left_mm   = pt_to_mm(left_x)
        top_mm    = pt_to_mm(top_y)
        right_mm  = pt_to_mm(page_w - right_x)
        bottom_mm = pt_to_mm(page_h - bottom_y)

        page_violations = []

        if left_mm < exp_left:
            page_violations.append(f'Left: {left_mm}mm (expected ≥{exp_left}mm)')
        if right_mm < exp_right:
            page_violations.append(f'Right: {right_mm}mm (expected ≥{exp_right}mm)')
        if top_mm < exp_top:
            page_violations.append(f'Top: {top_mm}mm (expected ≥{exp_top}mm)')
        if bottom_mm < exp_bottom:
            page_violations.append(f'Bottom: {bottom_mm}mm (expected ≥{exp_bottom}mm)')

        if page_violations:
            all_ok = False
            violations.append(
                f'Page {page_num+1}: ' + ' | '.join(page_violations)
            )

    passed = all_ok
    return {
        'name'   : 'Margins',
        'passed' : passed,
        'message': 'All margins are within required limits' if passed else
                   f'{len(violations)} page(s) have margin violations',
        'detail' : '\n'.join(violations) if violations else 'No violations'
    }


# ── Check 7: Column layout ────────────────────────────────────────────────────
def check_columns(doc, expected='single'):
    double_pages = []

    for page_num, page in enumerate(doc):
        blocks = page.get_text('dict')['blocks']

        text_blocks = [b for b in blocks if b['type'] == 0]
        if len(text_blocks) < 4:
            continue

        page_w    = page.rect.width
        mid_x     = page_w / 2

        # Count blocks clearly on left half vs right half
        left_col  = [b for b in text_blocks if b['bbox'][2] < mid_x - 20]
        right_col = [b for b in text_blocks if b['bbox'][0] > mid_x + 20]

        # If significant blocks exist on both sides — double column
        if len(left_col) >= 2 and len(right_col) >= 2:
            double_pages.append(page_num + 1)

    is_double = len(double_pages) > 0

    if expected == 'single':
        passed  = not is_double
        message = 'Single column layout confirmed' if passed else \
                  f'Double column detected on pages {double_pages}'
    else:
        passed  = is_double
        message = 'Double column layout confirmed' if passed else \
                  'Single column detected — expected double column'

    return {
        'name'   : 'Column layout',
        'passed' : passed,
        'message': message,
        'detail' : f'Expected: {expected} column | Double column pages: {double_pages if double_pages else "none"}'
    }


# ── Home ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
   return render_template('index.html')


# ── Main route ────────────────────────────────────────────────────────────────
@app.route('/check-pdf', methods=['POST'])
def check_pdf():

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files allowed'}), 400

    # Get user inputs from form
    expected_font   = request.form.get('font',           'Times New Roman')
    exp_top         = float(request.form.get('top',      25))
    exp_bottom      = float(request.form.get('bottom',   25))
    exp_left        = float(request.form.get('left',     25))
    exp_right       = float(request.form.get('right',    25))
    expected_cols   = request.form.get('columns',        'single')

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

    checks = [
        check_font_name(doc),
        check_chapter_title(doc),
        check_section_heading(doc),
        check_subsection_heading(doc),
        check_body_text(doc),
        check_margins(doc, exp_top, exp_bottom, exp_left, exp_right),
        check_columns(doc, expected_cols),
    ]

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