import io
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def txt_to_pdf(txt_content: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    x_margin = 40
    y_margin = 40
    y = height - y_margin

    for line in txt_content.splitlines():
        if y < y_margin:
            c.showPage()
            y = height - y_margin
        c.drawString(x_margin, y, line)
        y -= 14  # espaçamento entre linhas

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


st.set_page_config(page_title="TXT → PDF", layout="centered")
st.title("TXT → PDF")

uploaded = st.file_uploader("Envie um arquivo .txt", type=["txt"])

if uploaded:
    txt = uploaded.getvalue().decode("utf-8", errors="replace")

    st.text_area("Conteúdo do TXT", txt, height=300)

    if st.button("Gerar PDF"):
        pdf_bytes = txt_to_pdf(txt)
        st.download_button(
            label="Baixar PDF",
            data=pdf_bytes,
            file_name=uploaded.name.replace(".txt", ".pdf"),
            mime="application/pdf",
        )
