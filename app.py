import io
import time
import zipfile
from typing import List, Tuple

import requests
import streamlit as st
from PIL import Image

LABELARY_URL = "https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{w}x{h}/0/"


# -----------------------------
# Splitters
# -----------------------------
def split_by_dgr_blocks(text: str) -> List[str]:
    """
    Shopee costuma mandar 1 etiqueta por BLOCO que começa com ~DGR: (imagem Z64)
    e depois vem ^XA...^XZ (às vezes dois ^XA...^XZ seguidos).
    Aqui a gente separa por cada ocorrência de "~DGR:".
    """
    s = text.strip()
    if not s:
        return []

    idxs = []
    start = 0
    while True:
        i = s.find("~DGR:", start)
        if i == -1:
            break
        idxs.append(i)
        start = i + 5

    if not idxs:
        return []  # não é formato Shopee (sem ~DGR)

    blocks = []
    for k in range(len(idxs)):
        a = idxs[k]
        b = idxs[k + 1] if k + 1 < len(idxs) else len(s)
        block = s[a:b].strip()
        if block:
            blocks.append(block)

    return blocks


def split_by_xa_xz(text: str) -> List[str]:
    """
    Fallback: separa por ^XA...^XZ quando não existe ~DGR:
    """
    s = text.strip()
    if not s:
        return []

    blocks = []
    pos = 0
    while True:
        a = s.find("^XA", pos)
        if a == -1:
            break
        b = s.find("^XZ", a)
        if b == -1:
            blocks.append(s[a:].strip())
            break
        blocks.append(s[a : b + 3].strip())
        pos = b + 3

    return blocks


def split_labels(text: str) -> List[str]:
    blocks = split_by_dgr_blocks(text)
    if blocks:
        return blocks
    return split_by_xa_xz(text)


# -----------------------------
# Labelary
# -----------------------------
def zpl_to_png_bytes(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    url = LABELARY_URL.format(dpmm=dpmm, w=w_in, h=h_in)
    headers = {"Accept": "image/png"}

    for attempt in range(1, 6):
        r = requests.post(url, data=zpl.encode("utf-8"), headers=headers, timeout=90)

        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * attempt
            time.sleep(wait)
            continue

        if not r.ok:
            raise RuntimeError(f"Labelary {r.status_code}: {r.text[:800]}")

        return r.content

    raise RuntimeError("Labelary 429: limite excedido. Aguarde alguns minutos e tente novamente.")


@st.cache_data(show_spinner=False)
def cached_png(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    return zpl_to_png_bytes(zpl, dpmm, w_in, h_in)


# -----------------------------
# PNG -> PDF / ZIP
# -----------------------------
def pngs_to_pdf_bytes(png_items: List[Tuple[str, bytes]]) -> bytes:
    imgs = [Image.open(io.BytesIO(p)).convert("RGB") for _, p in png_items]
    if not imgs:
        raise ValueError("Nenhuma etiqueta foi renderizada.")
    out = io.BytesIO()
    imgs[0].save(out, format="PDF", save_all=True, append_images=imgs[1:])
    return out.getvalue()


def make_zip(png_items: List[Tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in png_items:
            z.writestr(name, data)
    return buf.getvalue()


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Shopee TXT (ZPL) → PDF", layout="centered")
st.title("Shopee TXT (ZPL) → PDF (multipágina)")

st.markdown(
    """
Esse app é feito pro TXT da Shopee: ele vem com **múltiplas etiquetas** e geralmente
cada etiqueta começa com `~DGR:` (imagem Z64) + depois `^XA...^XZ`.

Agora também aceita **ZIP contendo o TXT/ZPL**.
"""
)

col1, col2, col3 = st.columns(3)
with col1:
    dpmm = st.selectbox("Resolução (dpmm)", [8, 12, 24], index=0)
with col2:
    w_in = st.number_input("Largura (pol)", min_value=0.5, max_value=10.0, value=4.0, step=0.25)
with col3:
    h_in = st.number_input("Altura (pol)", min_value=0.5, max_value=15.0, value=6.0, step=0.25)

zpl_text = st.text_area("Cole o conteúdo do TXT/ZPL aqui", height=260)

uploaded = st.file_uploader(
    "Ou envie o TXT/ZPL ou um ZIP contendo o TXT",
    type=["txt", "zpl", "zip"]
)

if uploaded is not None:
    if uploaded.name.lower().endswith(".zip"):
        with zipfile.ZipFile(uploaded) as z:
            txt_files = [
                f for f in z.namelist()
                if f.lower().endswith((".txt", ".zpl"))
            ]

            if not txt_files:
                st.error("O ZIP não contém nenhum arquivo .txt ou .zpl")
                st.stop()

            file_name = txt_files[0]
            with z.open(file_name) as f:
                zpl_text = f.read().decode("utf-8", errors="replace")

            st.info(f"ZIP carregado: {uploaded.name}")
            st.success(f"Arquivo usado: {file_name}")
    else:
        zpl_text = uploaded.getvalue().decode("utf-8", errors="replace")
        st.info(f"Arquivo carregado: {uploaded.name}")

labels = split_labels(zpl_text) if zpl_text.strip() else []

if labels:
    st.caption(
        f"Etiquetas detectadas: {len(labels)} "
        f"(split por {'~DGR' if '~DGR:' in zpl_text else '^XA/^XZ'})"
    )

limit = st.number_input(
    "Converter quantas etiquetas (0 = todas)",
    min_value=0,
    max_value=max(0, len(labels)),
    value=0,
    step=1,
)

also_zip = st.checkbox("Também gerar ZIP com PNGs", value=False)

if st.button("Gerar PDF", disabled=not labels):
    try:
        to_convert = labels if limit == 0 else labels[:limit]
        png_items: List[Tuple[str, bytes]] = []

        with st.spinner("Renderizando etiquetas (PNG)..."):
            for i, block in enumerate(to_convert, start=1):
                png = cached_png(block, dpmm, w_in, h_in)
                png_items.append((f"label_{i:03d}.png", png))

        with st.spinner("Montando PDF multipágina..."):
            pdf_bytes = pngs_to_pdf_bytes(png_items)

        st.success("Conversão concluída.")

        st.download_button(
            "Baixar PDF",
            data=pdf_bytes,
            file_name="shopee_etiquetas.pdf",
            mime="application/pdf",
        )

        if also_zip:
            zip_bytes = make_zip(png_items)
            st.download_button(
                "Baixar ZIP (PNGs)",
                data=zip_bytes,
                file_name="shopee_etiquetas_png.zip",
                mime="application/zip",
            )

    except Exception as e:
        st.error(str(e))
        st.info(
            "Se a etiqueta cortar, ajuste largura/altura. "
            "Se der erro 429, aguarde alguns minutos e tente novamente."
        )
