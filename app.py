import time
import requests
import streamlit as st

# ===============================
# Configuração Labelary
# ===============================
LABELARY_URL = "https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{w}x{h}/0/"


def zpl_to_pdf_bytes(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    """
    Envia ZPL (texto) para o Labelary e retorna PDF em bytes.
    Possui retry para erro 429 (rate limit).
    """
    url = LABELARY_URL.format(dpmm=dpmm, w=w_in, h=h_in)
    headers = {"Accept": "application/pdf"}

    for attempt in range(1, 6):  # até 5 tentativas
        r = requests.post(
            url,
            data=zpl.encode("utf-8"),
            headers=headers,
            timeout=90,
        )

        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * attempt
            time.sleep(wait)
            continue

        if not r.ok:
            raise RuntimeError(f"Labelary {r.status_code}: {r.text[:600]}")

        return r.content

    raise RuntimeError("Labelary 429: limite excedido. Aguarde alguns minutos e tente novamente.")


@st.cache_data(show_spinner=False)
def cached_pdf(zpl: str, dpmm: int, w_in: float, h_in: float) -> bytes:
    return zpl_to_pdf_bytes(zpl, dpmm, w_in, h_in)


# ===============================
# UI Streamlit
# ===============================
st.set_page_config(page_title="ZPL (texto) → PDF", layout="centered")
st.title("ZPL (texto) → PDF")

st.markdown(
    """
Cole o **ZPL bruto** (mesmo vindo como texto) ou envie um `.txt` / `.zpl`.
O PDF será gerado usando o motor da impressora Zebra (Labelary).
"""
)

col1, col2, col3 = st.columns(3)
with col1:
    dpmm = st.selectbox(
        "Resolução (dpmm)",
        [8, 12, 24],
        index=0,
        help="8≈203dpi | 12≈300dpi | 24≈600dpi",
    )
with col2:
    w_in = st.number_input(
        "Largura (polegadas)",
        min_value=0.5,
        max_value=10.0,
        value=4.0,
        step=0.25,
    )
with col3:
    h_in = st.number_input(
        "Altura (polegadas)",
        min_value=0.5,
        max_value=12.0,
        value=6.0,
        step=0.25,
    )

zpl_text = st.text_area(
    "ZPL",
    height=300,
    placeholder="^XA\n...\n^XZ",
)

uploaded = st.file_uploader(
    "Ou envie um arquivo .txt ou .zpl",
    type=["txt", "zpl"],
)

if uploaded is not None:
    zpl_text = uploaded.getvalue().decode("utf-8", errors="replace")
    st.info(f"Arquivo carregado: {uploaded.name}")

st.caption(
    "Dica: se o PDF sair cortado, ajuste largura/altura acima até encaixar a etiqueta."
)

if st.button("Gerar PDF", disabled=not zpl_text.strip()):
    try:
        with st.spinner("Gerando PDF..."):
            pdf_bytes = cached_pdf(zpl_text, dpmm, w_in, h_in)

        st.success("PDF gerado com sucesso.")
        st.download_button(
            "Baixar PDF",
            data=pdf_bytes,
            file_name="etiqueta.pdf",
            mime="application/pdf",
        )

    except Exception as e:
        st.error(str(e))
