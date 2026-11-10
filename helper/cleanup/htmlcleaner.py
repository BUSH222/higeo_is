import re


def strip_document_wrapper(txt):
    """Remove the parts of a pasted Word/HTML document that must not end up inside a page.

    A pasted document brings its own <head> and <style> with it. Such a style block applies to the whole
    page, e.g. its `a:link` rule turns the navbar links blue. The text and markup of the body are kept.
    """
    txt = re.sub(r"<head\b.*?</head\s*>", "", txt, flags=re.IGNORECASE | re.DOTALL)
    txt = re.sub(r"<style\b.*?</style\s*>", "", txt, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"</?\s*(html|head|body|meta|title|link)\b[^>]*>", "", txt, flags=re.IGNORECASE)


def clean_html(txt):
    try:
        txt = strip_document_wrapper(txt)
        for _i in range(5):
            txt = re.sub(r"<\/?span[^>]*>", "", txt)
            txt = re.sub(r"<\/?/span[^>]*>", "", txt)
            txt = re.sub(r"<\/?div[^>]*>", "", txt)
            txt = re.sub("–", "-", txt)
            txt = re.sub(r"<script\b.*?</script\s*>", "", txt, flags=re.IGNORECASE | re.DOTALL)
            txt = re.sub(r"<a name[\S\s]*?>([\S\s]*?)<\/a>", r"\1", txt)
            while "MsoNormalCxSpFirst" in txt:
                txt = txt.replace("MsoNormalCxSpFirst", "GIN")
            while "MsoNormalCxSpMiddle" in txt:
                txt = txt.replace("MsoNormalCxSpMiddle", "GIN")
            while "MsoNormalCxSpLast" in txt:
                txt = txt.replace("MsoNormalCxSpLast", "GIN")
            while "&nbsp;" in txt:
                txt = txt.replace("&nbsp;", " ")
            while "</i><i>" in txt:
                txt = txt.replace("</i><i>", "")
            while "</b><b>" in txt:
                txt = txt.replace("</b><b>", "")
            while " <p>" in txt:
                txt = txt.replace(" <p>", "<p>")
            while " </p>" in txt:
                txt = txt.replace(" </p>", "</p>")
            while '"' in txt:
                txt = txt.replace('"', "")
            while "'" in txt:
                txt = txt.replace("'", "")
            while "&#774" in txt:
                txt = txt.replace("&#774", "й")
            while "<em>" in txt:
                txt = txt.replace("<em>", "<i>")
            while "</em>" in txt:
                txt = txt.replace("</em>", "</i>")
            while "  " in txt:
                txt = txt.replace("  ", " ")
            while "\n\n\n" in txt:
                txt = txt.replace("\n\n\n", "\n\n")
            while " " in txt:
                txt = txt.replace(" ", " ")
        return txt.strip()
    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return txt
