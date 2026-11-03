import hashlib,zipfile,html
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Pt
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from .db import DATA
FORMATS={'md','docx','xlsx','pptx','pdf','py','html','zip'}
MIME={'md':'text/markdown; charset=utf-8','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','pdf':'application/pdf','py':'text/x-python; charset=utf-8','html':'text/html; charset=utf-8','zip':'application/zip'}
def generate(org,task,run,fmt,text):
    folder=DATA/'artifacts'/org/task/run;folder.mkdir(parents=True,exist_ok=True)
    path=folder/('deliverable.'+fmt);lines=text.splitlines()
    if fmt=='md':path.write_text(text)
    elif fmt=='docx':
        d=Document()
        for l in lines:
            if l.startswith('# '):d.add_heading(l[2:],0)
            elif l.startswith('## '):d.add_heading(l[3:],1)
            else:d.add_paragraph(l)
        d.save(path)
    elif fmt=='xlsx':
        w=Workbook();sheet=w.active;sheet.title='交付记录';sheet.append(['行号','内容'])
        for i,l in enumerate(lines,1):sheet.append([i,"'"+l if l.startswith(('=','+','-','@','\t','\r')) else l])
        sheet.column_dimensions['B'].width=100;sheet.freeze_panes='A2';w.save(path)
    elif fmt=='pptx':
        p=Presentation()
        for start in range(0,len(lines),12):
            slide=p.slides.add_slide(p.slide_layouts[1]);slide.shapes.title.text='AI Universe · 工作交付';tf=slide.placeholders[1].text_frame;tf.text='\n'.join(lines[start:start+12])[:2500]
            for para in tf.paragraphs:para.font.size=Pt(16)
        p.save(path)
    elif fmt=='pdf':
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));c=canvas.Canvas(str(path));c.setTitle('AI Universe 成果');y=800
        for line in lines:
            for chunk in [line[i:i+44] for i in range(0,max(1,len(line)),44)]:
                if y<50:c.showPage();y=800
                c.setFont('STSong-Light',10);c.drawString(40,y,chunk);y-=16
        c.save()
    elif fmt=='py':path.write_text('# Local input analysis. No network or shell execution.\nimport json\nSOURCE = '+repr(text)+'\nprint(json.dumps({"characters": len(SOURCE), "lines": len(SOURCE.splitlines())}, ensure_ascii=False))\n')
    else:
        page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AI Universe 交付</title><style>body{font:16px system-ui;max-width:900px;margin:4rem auto;padding:2rem;background:#f4f2ec;color:#172d30}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>工作成果</h1><pre>'+html.escape(text)+'</pre></html>'
        if fmt=='html':path.write_text(page)
        else:
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('index.html',page);z.writestr('README.md','本地网页交付包。打开 index.html；内容是本地规则整理，并非模型编写项目。');z.writestr('report.md',text)
    raw=path.read_bytes();return str(path),hashlib.sha256(raw).hexdigest(),len(raw)
