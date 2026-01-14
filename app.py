import streamlit as st
import requests

LABELARY = "https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{w}x{h}/0/"


def zpl_to_pdf_bytes(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    url = LABELARY.format(dpmm=dpmm, w=w_in, h=h_in)
    headers = {"Accept": "application/pdf"}
    r = requests.post(url, data=zpl.encode("utf-8"), headers=headers, timeout=90)
    if not r.ok:
        raise RuntimeError(f"Labelary {r.status_code}: {r.text[:600]}")
    return r.content


st.set_page_config(page_title="ZPL (texto) → PDF", layout="centered")
st.title("ZPL (texto) → PDF")

col1, col2, col3 = st.columns(3)
with col1:
    dpmm = st.selectbox("Resolução (dpmm)", [8, 12, 24], index=0)  # 203/300/600dpi aprox
with col2:
    w_in = st.number_input("Largura (pol)", min_value=0.5, max_value=10.0, value=4.0, step=0.25)
with col3:
    h_in = st.number_input("Altura (pol)", min_value=0.5, max_value=12.0, value=6.0, step=0.25)

zpl_text = st.text_area("Cole o ZPL aqui", height=260, placeholder="^XA ... ^XZ")

uploaded = st.file_uploader("Ou envie um arquivo .txt/.zpl", type=["txt", "zpl"])

if uploaded is not None:
    zpl_text = uploaded.getvalue().decode("utf-8", errors="replace")
    st.info(f"Arquivo carregado: {uploaded.name}")

st.caption("Obs.: o PDF vai sair no tamanho que você definir acima (polegadas). Ajusta largura/altura se cortar.")

if st.button("Gerar PDF", disabled=not zpl_text.strip()):
    try:
        pdf_bytes = zpl_to_pdf_bytes(zpl_text, dpmm, w_in, h_in)
        st.success("Gerado.")
        st.download_button(
            "Baixar PDF",
            data=pdf_bytes,
            file_name="label.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(str(e))
