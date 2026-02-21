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

CYCLES = ["Cycle 2 — Lectorino & Lectorinette (CP/CE1/CE2)", "Cycle 3 — Lector & Lectrix (CM1/CM2/6ème)"]

ACCEPTED_MIME = {
    "application/pdf",
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"
}

DOCX_MIME = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.oasis.opendocument.text",
}

# ─── Fonctions utilitaires ────────────────────────────────────────────────────
def is_cycle2(cycle):
    return cycle.startswith("Cycle 2")

FICHE_STRUCTURE_C3 = """- TITRE DE LA SÉANCE & STRATÉGIE RETENUE
- JUSTIFICATION : Pourquoi cette stratégie est-elle adaptée à ce texte ?
- OBJECTIF PÉDAGOGIQUE : En lien avec les programmes.
- MODÉLISATION (Le "Haut-parleur sur la pensée") : Rédige le script détaillé de ce que l'enseignant dit aux élèves pour montrer comment il utilise la stratégie.
- DÉROULEMENT : Phases de pratique guidée et autonome.
- CONSEILS D'ÉTAYAGE : Pour les élèves en difficulté."""

FICHE_STRUCTURE_C2 = """- TITRE DE LA SÉANCE & PRIORITÉ TRAVAILLÉE
- JUSTIFICATION : Pourquoi cette priorité est-elle adaptée à ce texte et à ce niveau de classe ?
- OBJECTIF PÉDAGOGIQUE : En lien avec les programmes du cycle 2.
- TRAVAIL SUR LE VOCABULAIRE : Identifie 3 à 5 mots ou expressions du texte à travailler explicitement, avec une proposition d'activité courte pour les ancrer.
- MODÉLISATION (Le "Haut-parleur sur la pensée") : Rédige le script détaillé de ce que l'enseignant dit à voix haute pour montrer comment il comprend le texte — en insistant sur la narration orale et le "film intérieur".
- DÉROULEMENT : Phases collectives (lecture à voix haute par l'enseignant, reformulation orale) et phases guidées (activités de compréhension progressives).
- CONSEILS D'ÉTAYAGE : Pour les élèves en difficulté, avec des suggestions pour s'appuyer sur l'oral et les images."""

def build_prompt_auto(cycle):
    if is_cycle2(cycle):
        return f"""Agis en tant qu'expert pédagogique de la méthode Lectorino & Lectorinette pour le {cycle}.

Ce niveau travaille exclusivement des textes narratifs (albums de littérature jeunesse).
La méthode s'articule autour de 4 priorités — pas de "stratégies" numérotées comme au cycle 3.

Étape 1 : Analyse le texte fourni et choisis la priorité la plus pertinente parmi ces 4 :
1. Fluidité de lecture à voix haute (automatisation du décodage et lecture expressive).
2. Vocabulaire (enrichissement en réception et en production, suppléer aux mots inconnus).
3. Compétences narratives (construire une représentation mentale ; apprendre à raconter l'histoire).
4. Compréhension de l'implicite (reformulation des inférences causales ; explicitation des états mentaux des personnages : ce qu'ils pensent, ressentent, veulent).

Étape 2 : Rédige une fiche de préparation complète structurée ainsi :
{FICHE_STRUCTURE_C2}"""
    else:
        return f"""Agis en tant qu'expert pédagogique de la méthode Lector & Lectrix pour le {cycle}.

Étape 1 : Analyse le texte fourni et choisis la stratégie la plus pertinente parmi ces 6 :
1. Construire une représentation mentale (Faire le film).
2. Reformuler (Lire, c'est traduire).
3. L'autorégulation (Évaluer sa propre compréhension).
4. L'implicite et les inférences (Lire entre les lignes).
5. Les pensées des personnages (Buts, mobiles, sentiments).
6. Le choix de stratégies de réponse (Catégoriser les questions).

Étape 2 : Rédige une fiche de préparation complète structurée ainsi :
{FICHE_STRUCTURE_C3}"""

def build_prompt_manual(cycle, strat_num):
    if is_cycle2(cycle):
        c2_strategies = {
            "1": "Fluidité de lecture à voix haute (automatisation du décodage et lecture expressive)",
            "2": "Vocabulaire (enrichissement en réception et en production, suppléer aux mots inconnus)",
            "3": "Compétences narratives (construire une représentation mentale ; apprendre à raconter)",
            "4": "Compréhension de l'implicite (inférences causales et états mentaux des personnages)",
        }
        name = c2_strategies.get(strat_num, c2_strategies["1"])
        return f"""Agis en tant qu'expert pédagogique de la méthode Lectorino & Lectorinette pour le {cycle}.

L'enseignant a choisi de travailler la priorité suivante : "{strat_num}. {name}".
Ne remets pas en question ce choix ; construis directement la fiche en t'appuyant sur cette priorité appliquée au texte narratif fourni.

Rédige une fiche de préparation complète structurée ainsi :
{FICHE_STRUCTURE_C2}"""
    else:
        name = STRATEGIES[strat_num]
        return f"""Agis en tant qu'expert pédagogique de la méthode Lector & Lectrix pour le {cycle}.

L'enseignant a choisi de travailler la stratégie suivante : "{strat_num}. {name}".
Ne remets pas en question ce choix ; construis directement la fiche en t'appuyant sur cette stratégie appliquée au texte fourni.

Rédige une fiche de préparation complète structurée ainsi :
{FICHE_STRUCTURE_C3}"""

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

# ─── Extensions Word/ODT à détecter par nom de fichier ──────────────────────
DOCX_EXTENSIONS = {'.docx', '.doc', '.odt', '.rtf'}

def is_word_file(uploaded_file):
    if uploaded_file is None:
        return False
    name = uploaded_file.name.lower()
    return any(name.endswith(ext) for ext in DOCX_EXTENSIONS)

# ─── Réinitialisation ────────────────────────────────────────────────────────
def reset_tab(tab_key):
    # Incrémenter un compteur force Streamlit à recréer les widgets avec de nouvelles clés
    counter_key = f"reset_counter_{tab_key}"
    st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
    # Nettoyer le résultat
    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        del st.session_state[result_key]
    st.rerun()

# ─── Interface ────────────────────────────────────────────────────────────────
st.title("📖 Expert Lecteur / Lectrice")
st.caption("Outil pédagogique basé sur la méthode Lector & Lectrix")

st.markdown("""
<div class="mention">
📚 Cet outil génère des fiches de préparation inspirées des méthodes
<strong>Lector &amp; Lectrix</strong> (cycle 3) et <strong>Lectorino &amp; Lectorinette</strong> (cycle 2)
de <strong>Sylvie Cèbe et Roland Goigoux</strong> (Éditions Retz).
Il ne se substitue pas aux ouvrages et n'est pas affilié à leurs auteurs.
Son usage est pédagogique, gratuit et non commercial — il a vocation à encourager les enseignants
à s'approprier ces méthodes et à les intégrer dans leur pratique.
</div>
""", unsafe_allow_html=True)

tab_auto, tab_manual = st.tabs(["🤖 Stratégie automatique — l'IA choisit", "🎯 Stratégie choisie — je choisis"])

def render_tab(tab_key, is_manual=False):
    # Compteur de reset : chaque incrément force de nouvelles clés de widgets → tout se vide
    rc = st.session_state.get(f"reset_counter_{tab_key}", 0)

    # ── Ligne config : Cycle + bouton Réinitialiser ──────────────────────────
    col_cycle, col_reset = st.columns([4, 1])
    with col_cycle:
        cycle = st.selectbox("Cycle", CYCLES, index=1, key=f"cycle_{tab_key}_{rc}")
    with col_reset:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("🔄 Réinitialiser", key=f"reset_{tab_key}_{rc}", help="Vider le formulaire et recommencer"):
            reset_tab(tab_key)
        st.markdown("</div>", unsafe_allow_html=True)

    if is_manual:
        c2_mode = is_cycle2(cycle)
        if c2_mode:
            strat_options_c2 = {
                "1": "Fluidité de lecture à voix haute",
                "2": "Vocabulaire (réception et production)",
                "3": "Compétences narratives (représentation mentale + raconter)",
                "4": "Compréhension de l'implicite (inférences + états mentaux)",
            }
            opts = [f"{k} · {v}" for k, v in strat_options_c2.items()]
            label = "🎯 Priorité Lectorino & Lectorinette à travailler"
        else:
            opts = [f"{k} · {v}" for k, v in STRATEGIES.items()]
            label = "🎯 Stratégie Lector & Lectrix à travailler"
        strat_choice = st.selectbox(label, opts, key=f"strat_select_{rc}")
        strat_num = strat_choice[0]

    st.markdown("**Support de lecture**")

    # ── Upload avec filtre étendu pour capturer les docx/odt ─────────────────
    uploaded = st.file_uploader(
        "PDF, JPEG, PNG, WebP, GIF",
        type=["pdf", "jpg", "jpeg", "png", "webp", "gif", "heic",
              "docx", "doc", "odt", "rtf"],
        key=f"file_{tab_key}_{rc}"
    )

    # ── Message personnalisé Word/ODT ─────────────────────────────────────────
    if is_word_file(uploaded):
        st.markdown("""
        <div style="background:#fffbe6; border-left:5px solid #c8972a; border-radius:6px;
                    padding:14px 18px; margin-bottom:10px; font-size:0.93em;">
            💡 <strong>Fichier Word / ODT détecté</strong><br><br>
            Ce format ne peut pas être envoyé directement à l'IA.<br>
            La solution la plus simple :<br>
            <strong>Ouvrez votre document → Ctrl+A → Ctrl+C</strong><br>
            puis collez le texte dans la zone ci-dessous 👇
        </div>
        """, unsafe_allow_html=True)
        uploaded = None

    st.markdown("<p style='text-align:center; color:#aaa; font-weight:bold; margin:4px 0;'>— OU —</p>",
                unsafe_allow_html=True)
    pasted = st.text_area("Collez votre texte ici", height=120, key=f"text_{tab_key}_{rc}")

    # ── Avertissement conflit fichier + texte ─────────────────────────────────
    both_filled = uploaded is not None and pasted.strip()
    if both_filled:
        st.warning("⚠️ Un fichier **et** du texte collé sont présents. "
                   "L'appli utilisera uniquement le **fichier**. "
                   "Videz la zone de texte si vous souhaitez utiliser le texte collé.")

    btn_label = "🎯 Générer la fiche avec cette stratégie" if is_manual else "🚀 Lancer l'analyse — l'IA choisit la stratégie"
    color = "#5a3472" if is_manual else "#1a2e4a"

    st.markdown(f"""
    <style>div[data-testid="stButton"] button[kind="primary"] {{
        background-color: {color}; color: white;
    }}</style>""", unsafe_allow_html=True)

    if st.button(btn_label, type="primary", key=f"btn_{tab_key}_{rc}"):
        if not uploaded and not pasted.strip():
            st.error("Veuillez charger un fichier ou coller un texte.")
            return

        with st.spinner("⏳ Analyse et rédaction de la fiche en cours…"):
            try:
                if is_manual:
                    prompt = build_prompt_manual(cycle, strat_num)
                    if is_cycle2(cycle):
                        strat_label = f" · Priorité {strat_num}"
                    else:
                        strat_label = f" · Stratégie {strat_num}"
                else:
                    prompt = build_prompt_auto(cycle)
                    strat_label = " · Stratégie automatique"

                # Priorité au fichier si les deux sont présents
                effective_text = None if uploaded else pasted.strip() or None
                result = call_gemini(prompt, uploaded, effective_text)
                st.session_state[f"result_{tab_key}"] = (result, cycle, strat_label)
            except Exception as e:
                st.error(f"Erreur Gemini : {e}")

    if f"result_{tab_key}" in st.session_state:
        result, cycle_saved, strat_saved = st.session_state[f"result_{tab_key}"]
        st.markdown("---")
        st.markdown("**Fiche de séance générée**")
        st.markdown(result)

        fname = f"Fiche_Lector_{cycle_saved.replace(' ','_')}{strat_saved.replace(' ','_')}.docx"
        docx_bytes = export_word(result, cycle_saved, strat_saved)
        st.download_button(
            label="📥 Télécharger la Fiche (Word .docx)",
            data=docx_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"dl_{tab_key}_{rc}"
        )

with tab_auto:
    render_tab("auto", is_manual=False)

with tab_manual:
    render_tab("manual", is_manual=True)
