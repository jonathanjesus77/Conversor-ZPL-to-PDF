import io
import zipfile
from pathlib import Path

import requests
import streamlit as st
from PIL import Image


LABELARY_URL = "https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{w}x{h}/0/"


def zpl_to_png_bytes(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    url = LABELARY_URL.format(dpmm=dpmm, w=w_in, h=h_in)
    headers = {"Accept": "image/png"}
    r = requests.post(url, data=zpl.encode("utf-8"), headers=headers, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Labelary error {r.status_code}: {r.text[:400]}")
    return r.content


def png_bytes_to_pdf_bytes(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PDF")
    return out.getvalue()


st.set_page_config(page_title="ZPL → PDF", layout="centered")
st.title("ZPL → PDF")

col1, col2, col3 = st.columns(3)
with col1:
    dpmm = st.selectbox("Resolução (dpmm)", [8, 12, 24], index=0)  # 203/300/600 dpi aprox
with col2:
    w_in = st.number_input("Largura (pol)", min_value=0.5, max_value=10.0, value=4.0, step=0.25)
with col3:
    h_in = st.number_input("Altura (pol)", min_value=0.5, max_value=12.0, value=6.0, step=0.25)

uploaded = st.file_uploader("Envie um .zpl ou vários .zpl", type=["zpl"], accept_multiple_files=True)

if uploaded:
    if st.button("Converter"):
        pdfs = []
        for f in uploaded:
            zpl = f.getvalue().decode("utf-8", errors="replace")
            png = zpl_to_png_bytes(zpl, dpmm, w_in, h_in)
            pdf = png_bytes_to_pdf_bytes(png)
            pdfs.append((Path(f.name).stem + ".pdf", pdf))

        if len(pdfs) == 1:
            name, data = pdfs[0]
            st.success("Convertido.")
            st.download_button("Baixar PDF", data=data, file_name=name, mime="application/pdf")
        else:
            # zip com todos os pdfs
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for name, data in pdfs:
                    z.writestr(name, data)
            st.success("Convertidos.")
            st.download_button("Baixar ZIP", data=buf.getvalue(), file_name="pdfs.zip", mime="application/zip")
