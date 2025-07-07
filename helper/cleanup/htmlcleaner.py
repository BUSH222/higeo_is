import re


def clean_html(txt):
    try:
        rightstyle = '''<style>
<!--
 /* Style Definitions */
p.GIN
    {margin-top:0cm;
    margin-right:0cm;
    margin-bottom:0cm;
    margin-left:36.0pt;
    text-align:justify;
    text-indent:-36.0pt;
    punctuation-wrap:simple;
    text-autospace:none;
    font-size:12.0pt;
    font-family:Times New Roman CYR,serif;}
-->
</style>'''
        for i in range(5):
            txt = re.sub(r'<\/?span[^>]*>', '', txt)
            txt = re.sub(r'<\/?/span[^>]*>', '', txt)
            txt = re.sub(r'<\/?div[^>]*>', '', txt)
            txt = re.sub(r'<style>.*?</style>', rightstyle, txt, flags=re.DOTALL)
            txt = re.sub(u"\u2013", "-", txt)
            txt = re.sub(r'<script(.|\n)*script>', '', txt)
            txt = re.sub(r'<a name[\S\s]*?>([\S\s]*?)<\/a>', r'\1', txt)
            txt = re.sub('<body lang=RU link=.*?>', '', txt)
            txt = re.sub('<title>.*?</title>',
                         '<title>Информационная система: История геологии и горного дела ГИН РАН</title>',
                         txt, flags=re.DOTALL)
            while '<body lang=RU link=blue vlink=#954F72 style=word-wrap:break-word>' in txt:
                txt = txt.replace('<body lang=RU link=blue vlink=#954F72 style=word-wrap:break-word>',
                                  '<body lang=RU>')
            while 'MsoNormalCxSpFirst' in txt:
                txt = txt.replace('MsoNormalCxSpFirst', 'GIN')
            while 'MsoNormalCxSpMiddle' in txt:
                txt = txt.replace('MsoNormalCxSpMiddle', 'GIN')
            while 'MsoNormalCxSpLast' in txt:
                txt = txt.replace('MsoNormalCxSpLast', 'GIN')
            while 'MsoNormalCxSpLast' in txt:
                txt = txt.replace('MsoNormal', 'GIN')
            while '&nbsp;' in txt:
                txt = txt.replace('&nbsp;', ' ')
            while '</i><i>' in txt:
                txt = txt.replace('</i><i>', '')
            while '</b><b>' in txt:
                txt = txt.replace('</b><b>', '')
            while ' <p>' in txt:
                txt = txt.replace(' <p>', '<p>')
            while ' </p>' in txt:
                txt = txt.replace(' </p>', '</p>')
            while '"' in txt:
                txt = txt.replace('"', '')
            while "'" in txt:
                txt = txt.replace("'", '')
            while "&#774" in txt:
                txt = txt.replace("&#774", 'й')
            while '<em>' in txt:
                txt = txt.replace('<em>', '<i>')
            while '</em>' in txt:
                txt = txt.replace('</em>', '</i>')
            while '  ' in txt:
                txt = txt.replace('  ', ' ')
            while '\n\n\n' in txt:
                txt = txt.replace('\n\n\n', '\n\n')
            while u"\u00A0" in txt:
                txt = txt.replace(u"\u00A0", ' ')
            while "<meta name=Generator content=Microsoft Word 15 (filtered)>" in txt:
                txt = txt.replace("<meta name=Generator content=Microsoft Word 15 (filtered)>", ' ')
            while "<body lang=RU link=blue vlink=purple style=word-wrap:break-word>" in txt:
                txt = txt.replace("<body lang=RU link=blue vlink=purple style=word-wrap:break-word>", '<body lang=RU>')
    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return txt
