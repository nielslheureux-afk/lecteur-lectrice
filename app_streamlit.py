import streamlit as st
import google.generativeai as genai
import base64
import zipfile
import io
import re
from xml.sax.saxutils import escape as xml_escape

# ─── Configuration page ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Expert Lecteur / Lectrice",
    page_icon="📖",
    layout="centered"
)

# ─── CSS personnalisé ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { max-width: 860px; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 24px;
        font-weight: bold;
    }
    .mention {
        background: #fffdf5;
        border-left: 5px solid #c8972a;
        border-radius: 6px;
        padding: 12px 18px;
        font-size: 0.88em;
        color: #555;
        margin-bottom: 20px;
    }
    .result-box {
        background: #f8f9fa;
        border-left: 5px solid #c8972a;
        border-radius: 6px;
        padding: 20px;
        line-height: 1.7;
    }
</style>
""", unsafe_allow_html=True)

# ─── Clé API (secret Streamlit) ───────────────────────────────────────────────
try:
    API_KEY = st.secrets["GEMINI_API_KEY_2"]
except Exception:
    API_KEY = None

if not API_KEY:
    st.error("⚠️ Clé API Gemini manquante. Ajoutez GEMINI_API_KEY_2 dans les secrets Streamlit.")
    st.stop()

genai.configure(api_key=API_KEY)

# ─── Constantes ───────────────────────────────────────────────────────────────
STRATEGIES = {
    "1": "Construire une représentation mentale (Faire le film)",
    "2": "Reformuler (Lire, c'est traduire)",
    "3": "L'autorégulation (Évaluer sa propre compréhension)",
    "4": "L'implicite et les inférences (Lire entre les lignes)",
    "5": "Les pensées des personnages (Buts, mobiles, sentiments)",
    "6": "Le choix de stratégies de réponse (Catégoriser les questions)",
}

CYCLES = ["Cycle 2 (CE1/CE2)", "Cycle 3 (CM1/CM2/6ème)"]

ACCEPTED_MIME = {
    "application/pdf",
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"
}

DOCX_MIME = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.oasis.opendocument.text",
}

PROMPT_BASE = """Agis en tant qu'expert pédagogique Lector/Lectrix pour le {cycle}.

Rédige une fiche de préparation complète (1 à 2 pages) structurée ainsi :
- TITRE DE LA SÉANCE & STRATÉGIE RETENUE
- JUSTIFICATION : Pourquoi cette stratégie est-elle adaptée à ce texte ?
- OBJECTIF PÉDAGOGIQUE : En lien avec les programmes.
- MODÉLISATION (Le "Haut-parleur sur la pensée") : Rédige le script détaillé de ce que l'enseignant dit aux élèves pour montrer comment il utilise la stratégie.
- DÉROULEMENT : Phases de pratique guidée et autonome.
- CONSEILS D'ÉTAYAGE : Pour les élèves en difficulté."""

# ─── Fonctions utilitaires ────────────────────────────────────────────────────
def build_prompt_auto(cycle):
    return f"""Agis en tant qu'expert pédagogique Lector/Lectrix pour le {cycle}.

Étape 1 : Analyse le texte fourni et choisis la stratégie la plus pertinente parmi ces 6 :
1. Construire une représentation mentale (Faire le film).
2. Reformuler (Lire, c'est traduire).
3. L'autorégulation (Évaluer sa propre compréhension).
4. L'implicite et les inférences (Lire entre les lignes).
5. Les pensées des personnages (Buts, mobiles, sentiments).
6. Le choix de stratégies de réponse (Catégoriser les questions).

Étape 2 : {PROMPT_BASE.format(cycle=cycle)}"""

def build_prompt_manual(cycle, strat_num):
    name = STRATEGIES[strat_num]
    return f"""Agis en tant qu'expert pédagogique Lector/Lectrix pour le {cycle}.

L'enseignant a choisi de travailler la stratégie suivante : "{strat_num}. {name}".
Ne remets pas en question ce choix ; construis directement la fiche en t'appuyant sur cette stratégie appliquée au texte fourni.

{PROMPT_BASE.format(cycle=cycle)}"""

def call_gemini(prompt, uploaded_file=None, pasted_text=None):
    model = genai.GenerativeModel("gemini-2.5-flash")
    parts = [prompt]
    if pasted_text:
        parts.append("Voici le texte à analyser : " + pasted_text)
    elif uploaded_file is not None:
        file_bytes = uploaded_file.read()
        parts.append({"mime_type": uploaded_file.type, "data": file_bytes})
    response = model.generate_content(parts)
    return response.text

# ─── Export Word ──────────────────────────────────────────────────────────────
def parse_inline(line):
    segs = []
    last = 0
    for m in re.finditer(r'\*\*(.*?)\*\*', line):
        if m.start() > last:
            segs.append((line[last:m.start()], False))
        segs.append((m.group(1), True))
        last = m.end()
    if last < len(line):
        segs.append((line[last:], False))
    return segs

def make_run(text, bold, sz, color=""):
    if not text:
        return ""
    b = "<w:b/>" if bold else ""
    c = f'<w:color w:val="{color}"/>' if color else ""
    return (f'<w:r><w:rPr>{b}<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>{c}</w:rPr>'
            f'<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r>')

def build_para(line):
    stripped = re.sub(r'^#+\s*', '', line).strip()
    if not stripped:
        return ''
    clean = re.sub(r'\*\*', '', stripped)
    is_h = line.startswith('#') or bool(re.match(r'^[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ0-9\s\-\/&:«»"\'()]{8,}$', clean))
    sz = '28' if is_h else '24'
    col = '1a2e4a' if is_h else ''
    sp = '<w:spacing w:before="240" w:after="80"/>' if is_h else '<w:spacing w:before="0" w:after="60"/>'
    runs = ''.join(make_run(t, is_h or b, sz, col) for t, b in parse_inline(stripped))
    return f'<w:p><w:pPr>{sp}</w:pPr>{runs}</w:p>'

def export_word(content, cycle, strat_label):
    header = (
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="120"/></w:pPr>'
        '<w:r><w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/>'
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:color w:val="1a2e4a"/></w:rPr>'
        '<w:t>FICHE DE PRÉPARATION LECTOR/LECTRIX</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="360"/></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/>'
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:color w:val="555555"/></w:rPr>'
        f'<w:t>{xml_escape(cycle + strat_label)}</w:t></w:r></w:p>'
    )
    body = header + ''.join(build_para(l) for l in content.split('\n'))
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<w:body>{body}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
        '</w:sectPr></w:body></w:document>'
    )
    ct_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="word/document.xml"/>'
        '</Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct_xml)
        z.writestr('_rels/.rels', rels_xml)
        z.writestr('word/document.xml', doc_xml)
        z.writestr('word/_rels/document.xml.rels',
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
    buf.seek(0)
    return buf.read()

# ─── Interface ────────────────────────────────────────────────────────────────
st.title("📖 Expert Lecteur / Lectrice")
st.caption("Outil pédagogique basé sur la méthode Lector & Lectrix")

st.markdown("""
<div class="mention">
📚 Cet outil génère des fiches de préparation inspirées de la méthode
<strong>Lector &amp; Lectrix</strong> de <strong>Sylvie Cèbe et Roland Goigoux</strong> (Éditions Retz).
Il ne se substitue pas à l'ouvrage et n'est pas affilié à ses auteurs.
Son usage est pédagogique, gratuit et non commercial — il a vocation à encourager les enseignants
à s'approprier cette méthode et à l'intégrer dans leur pratique.
</div>
""", unsafe_allow_html=True)

tab_auto, tab_manual = st.tabs(["🤖 Stratégie automatique — l'IA choisit", "🎯 Stratégie choisie — je choisis"])

def render_tab(tab_key, is_manual=False):
    col1, col2 = st.columns([2, 1])
    with col1:
        cycle = st.selectbox("Cycle", CYCLES, index=1, key=f"cycle_{tab_key}")
    if is_manual:
        strat_options = [f"{k} · {v}" for k, v in STRATEGIES.items()]
        strat_choice = st.selectbox("🎯 Stratégie à travailler", strat_options, key="strat_select")
        strat_num = strat_choice[0]

    st.markdown("**Support de lecture**")
    uploaded = st.file_uploader(
        "PDF, JPEG, PNG, WebP, GIF",
        type=["pdf", "jpg", "jpeg", "png", "webp", "gif", "heic"],
        key=f"file_{tab_key}"
    )

    # Avertissement Word/ODT
    if uploaded and uploaded.type in DOCX_MIME:
        st.warning("💡 **Fichier Word / ODT détecté.** Ce format n'est pas supporté directement.\n\n"
                   "Solution simple : ouvrez le document → **Ctrl+A → Ctrl+C** puis collez le texte ci-dessous 👇")
        uploaded = None

    st.markdown("<p style='text-align:center; color:#aaa; font-weight:bold; margin:4px 0;'>— OU —</p>",
                unsafe_allow_html=True)
    pasted = st.text_area("Collez votre texte ici", height=120, key=f"text_{tab_key}")

    btn_label = "🎯 Générer la fiche avec cette stratégie" if is_manual else "🚀 Lancer l'analyse — l'IA choisit la stratégie"
    color = "#5a3472" if is_manual else "#1a2e4a"

    st.markdown(f"""
    <style>div[data-testid="stButton"] button[kind="primary"] {{
        background-color: {color}; color: white;
    }}</style>""", unsafe_allow_html=True)

    if st.button(btn_label, type="primary", key=f"btn_{tab_key}"):
        if not uploaded and not pasted.strip():
            st.error("Veuillez charger un fichier ou coller un texte.")
            return

        with st.spinner("⏳ Analyse et rédaction de la fiche en cours…"):
            try:
                if is_manual:
                    prompt = build_prompt_manual(cycle, strat_num)
                    strat_label = f" · Stratégie {strat_num}"
                else:
                    prompt = build_prompt_auto(cycle)
                    strat_label = " · Stratégie automatique"

                result = call_gemini(prompt, uploaded, pasted.strip() or None)
                st.session_state[f"result_{tab_key}"] = (result, cycle, strat_label)
            except Exception as e:
                st.error(f"Erreur Gemini : {e}")

    if f"result_{tab_key}" in st.session_state:
        result, cycle_saved, strat_saved = st.session_state[f"result_{tab_key}"]
        st.markdown("---")
        st.markdown("**Fiche de séance générée**")
        # Affichage avec rendu markdown natif de Streamlit
        st.markdown(result)

        fname = f"Fiche_Lector_{cycle_saved.replace(' ','_')}{strat_saved.replace(' ','_')}.docx"
        docx_bytes = export_word(result, cycle_saved, strat_saved)
        st.download_button(
            label="📥 Télécharger la Fiche (Word .docx)",
            data=docx_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"dl_{tab_key}"
        )

with tab_auto:
    render_tab("auto", is_manual=False)

with tab_manual:
    render_tab("manual", is_manual=True)
