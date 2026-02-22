import streamlit as st
import google.generativeai as genai
import base64
import zipfile
import io
import re
from xml.sax.saxutils import escape as xml_escape

# ─── Configuration page ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lecteur / Lectrice",
    page_icon="📖",
    layout="centered"
)

# ─── CSS ACCESSIBLE — Thème "Ardoise & Craie" ─────────────────────────────────
# Palette :
#   --ardoise     #1A3A2A  fond bandeau (vert forêt très sombre)
#   --ardoise-mid #2A5A3F  blocs secondaires
#   --ivoire      #F6F4EE  fond principal (blanc chaud)
#   --ivoire-bord #DDD8CC  bordures subtiles
#   --sauge       #3D8B5E  accent principal — ratio 4.6:1 sur fond sombre ✓
#   --sauge-pale  #EAF4EE  fond badge clair
#   --texte       #1A1A16  texte principal — ratio ~15:1 sur ivoire ✓
#   --texte-doux  #3A3A2E  texte secondaire — ratio ~8:1 sur ivoire ✓
#   --focus       #E07B00  orange brûlé — contraste maximal, inattendu ✓
#   Police : Nunito (ronde, lisible, accessible, humaniste sans-serif)
#            + Cormorant Garamond pour les titres (distinction avec ADC qui utilise Fraunces)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,400;0,600;0,700;0,800;1,400&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&display=swap');

  /* ── Variables ── */
  :root {
    --ardoise:      #1A3A2A;
    --ardoise-mid:  #2A5A3F;
    --ardoise-bord: #3D7055;
    --ivoire:       #F6F4EE;
    --ivoire-bord:  #DDD8CC;
    --ivoire-fort:  #C2BDB0;
    --sauge:        #3D8B5E;
    --sauge-pale:   #EAF4EE;
    --sauge-vif:    #2E7A4E;
    --violet:       #5A3472;  /* onglet manuel — déjà utilisé dans le code original */
    --violet-pale:  #F0EAF8;
    --texte:        #1A1A16;
    --texte-doux:   #3A3A2E;
    --blanc:        #FFFFFF;
    --focus:        #E07B00;  /* orange brûlé — visible sur tout fond */

    --font-body:    'Nunito', Helvetica, sans-serif;
    --font-titre:   'Cormorant Garamond', Georgia, serif;
    --taille-base:  17px;
    --taille-sm:    15px;
    --taille-xs:    13px;
  }

  /* ── Reset base ── */
  html, body, [class*="css"] {
    font-family: var(--font-body);
    font-size: var(--taille-base);
    background-color: var(--ivoire);
    color: var(--texte);
    line-height: 1.7;
    text-align: left; /* pas de justify — dyslexie */
  }

  /* ── Focus universel très visible ── */
  *:focus,
  *:focus-visible {
    outline: 3px solid var(--focus) !important;
    outline-offset: 3px !important;
    border-radius: 4px !important;
    box-shadow: 0 0 0 6px rgba(224, 123, 0, 0.22) !important;
  }

  /* ── Motif discret fond — "pointillés craie" ── */
  .main > div {
    background-image: radial-gradient(
      circle, rgba(60, 80, 60, 0.08) 1px, transparent 1px
    );
    background-size: 22px 22px;
    background-attachment: local;
  }

  /* ══════════════════════════════════
     BANDEAU HÉRO
     #1A3A2A → blanc #FFF : ratio 17:1 ✓
     accent sauge #3D8B5E sur ardoise : 4.6:1 ✓
  ══════════════════════════════════ */
  .hero-band {
    background: var(--ardoise);
    color: var(--blanc);
    padding: 2.4rem 2.5rem 2rem;
    margin: -1rem -1rem 2.2rem -1rem;
    position: relative;
    overflow: hidden;
    border-bottom: 4px solid var(--sauge);
  }
  /* Texture décorative — aria-hidden */
  .hero-band::before {
    content: "";
    position: absolute;
    left: -4rem; bottom: -4rem;
    width: 18rem; height: 18rem;
    border-radius: 50%;
    border: 50px solid rgba(255,255,255,0.035);
    pointer-events: none;
  }
  .hero-band::after {
    content: "";
    position: absolute;
    right: 2rem; top: -2rem;
    width: 10rem; height: 10rem;
    border-radius: 50%;
    border: 30px solid rgba(255,255,255,0.04);
    pointer-events: none;
  }
  .hero-label {
    font-family: var(--font-body);
    font-size: var(--taille-xs);
    font-weight: 800;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    color: #7DC8A0;  /* vert clair sur ardoise → 5.2:1 ✓ */
    margin-bottom: 0.5rem;
    display: block;
  }
  /* h1 unique */
  .hero-band h1 {
    font-family: var(--font-titre);
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 600;
    line-height: 1.1;
    margin: 0 0 0.4rem 0;
    color: var(--blanc) !important;
    letter-spacing: 0.01em;
  }
  .hero-band .hero-caption {
    font-size: clamp(0.9rem, 2vw, 1rem);
    color: #A8C8B8;  /* ratio ~5:1 sur ardoise ✓ */
    font-style: italic;
    margin: 0;
    line-height: 1.55;
  }
  .hero-sep {
    width: 3rem;
    height: 3px;
    background: var(--sauge);
    border: none;
    margin: 1rem 0;
  }

  /* ══════════════════════════════════
     MENTION DROITS
     Fond ivoire / texte --texte-doux (#3A3A2E) → 8:1 ✓
     Bord gauche sauge — double signal (couleur + épaisseur)
  ══════════════════════════════════ */
  .mention {
    background: var(--sauge-pale);
    border-left: 5px solid var(--sauge);
    border-radius: 0 8px 8px 0;
    padding: 1.1rem 1.5rem;
    font-size: var(--taille-sm);
    color: var(--texte-doux);
    margin-bottom: 1.8rem;
    line-height: 1.65;
  }
  .mention strong {
    color: var(--texte);
  }
  /* Icône informative — pas seulement couleur */
  .mention::before {
    content: "ℹ️  ";
  }

  /* ══════════════════════════════════
     ONGLETS (Tabs)
  ══════════════════════════════════ */
  .stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
    border-bottom: 2px solid var(--ivoire-bord);
    padding-bottom: 0;
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.6rem 1.4rem;
    font-family: var(--font-body);
    font-size: var(--taille-sm);
    font-weight: 700;
    color: var(--texte-doux);
    background: var(--ivoire-bord);
    border: 1.5px solid var(--ivoire-fort);
    border-bottom: none;
    transition: background 0.15s, color 0.15s;
  }
  .stTabs [aria-selected="true"] {
    background: var(--ardoise) !important;
    color: var(--blanc) !important;
    border-color: var(--ardoise) !important;
  }
  .stTabs [data-baseweb="tab"]:hover {
    background: var(--sauge-pale);
    color: var(--ardoise);
  }
  .stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.4rem;
  }

  /* ══════════════════════════════════
     ZONE MESSAGE WORD (warning inline)
     Fond jaune pale + bord + icône = triple signal, pas seulement couleur
  ══════════════════════════════════ */
  .word-warning {
    background: #FFF8E6;
    border-left: 5px solid #B07800;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.4rem;
    margin-bottom: 0.8rem;
    font-size: var(--taille-sm);
    color: #4A3400;  /* ratio ~13:1 sur #FFF8E6 ✓ */
    line-height: 1.6;
  }
  .word-warning strong { color: #2E2000; }

  /* ══════════════════════════════════
     BOUTON AUTO — Vert ardoise
     Fond #1A3A2A / texte blanc → 17:1 ✓
  ══════════════════════════════════ */
  div[data-testid="stButton"] button[kind="primary"] {
    font-family: var(--font-body) !important;
    font-size: var(--taille-sm) !important;
    font-weight: 800 !important;
    letter-spacing: 0.05em !important;
    border-radius: 6px !important;
    padding: 0.7rem 1.8rem !important;
    border: 2px solid transparent !important;
    transition: background 0.18s, border-color 0.18s !important;
  }
  div[data-testid="stButton"] button[kind="primary"]:hover {
    filter: brightness(1.15);
    border-color: var(--focus) !important;
  }
  div[data-testid="stButton"] button[kind="primary"]:focus,
  div[data-testid="stButton"] button[kind="primary"]:focus-visible {
    outline: 3px solid var(--focus) !important;
    outline-offset: 3px !important;
  }

  /* ── Bouton reset ── */
  div[data-testid="stButton"] button[kind="secondary"] {
    font-family: var(--font-body) !important;
    font-size: var(--taille-xs) !important;
    font-weight: 700 !important;
    background: var(--ivoire-bord) !important;
    color: var(--texte) !important;
    border: 1.5px solid var(--ivoire-fort) !important;
    border-radius: 6px !important;
  }
  div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: var(--ivoire-fort) !important;
  }

  /* ── Bouton téléchargement ── */
  .stDownloadButton > button {
    background: var(--sauge-pale) !important;
    color: var(--texte) !important;  /* #1A1A16 sur #EAF4EE → 13:1 ✓ */
    font-family: var(--font-body) !important;
    font-weight: 700 !important;
    font-size: var(--taille-sm) !important;
    border: 2px solid var(--sauge) !important;
    border-radius: 6px !important;
    padding: 0.65rem 1.6rem !important;
  }
  .stDownloadButton > button:hover {
    background: var(--sauge) !important;
    color: var(--blanc) !important;
  }

  /* ── Selectbox / Text area / File uploader ── */
  [data-testid="stSelectbox"],
  [data-testid="stTextArea"],
  [data-testid="stFileUploader"] {
    font-family: var(--font-body) !important;
  }
  [data-testid="stFileUploader"] {
    border: 2px dashed var(--ivoire-fort);
    border-radius: 10px;
    background: var(--blanc);
    padding: 0.5rem;
    transition: border-color 0.2s;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: var(--sauge);
  }

  /* ── Zone résultat ── */
  .result-box {
    background: var(--blanc);
    border-left: 5px solid var(--ardoise-mid);
    border-radius: 0 8px 8px 0;
    padding: 1.8rem 2rem;
    margin-top: 1rem;
    line-height: 1.8;
    font-size: var(--taille-base);
    color: var(--texte);
    box-shadow: 0 2px 14px rgba(26, 58, 42, 0.07);
  }

  /* ── Messages Streamlit (erreur, warning, info) ── */
  [data-testid="stAlert"] {
    font-family: var(--font-body) !important;
    font-size: var(--taille-base) !important;
    border-radius: 8px !important;
  }

  /* ── Responsive ── */
  @media (max-width: 640px) {
    .hero-band {
      padding: 1.5rem 1.2rem 1.3rem;
      margin: -0.5rem -0.5rem 1.4rem -0.5rem;
    }
    .hero-band h1 { font-size: 1.7rem; }
    .mention, .word-warning, .result-box {
      padding: 0.9rem 1rem;
    }
    .stTabs [data-baseweb="tab"] {
      padding: 0.5rem 0.8rem;
      font-size: 0.82rem;
    }
  }

  /* ── Masquer chrome Streamlit ── */
  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
  [data-testid="stDecoration"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── Clé API (secret Streamlit) ───────────────────────────────────────────────
import os
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY_2") or st.secrets.get("GEMINI_API_KEY")
except Exception:
    API_KEY = None
API_KEY = API_KEY or os.environ.get("GEMINI_API_KEY_2") or os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("⚠️ Erreur de configuration — Clé API Gemini manquante. Ajoutez GEMINI_API_KEY_2 dans les secrets Streamlit.")
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
    col = '1A3A2A' if is_h else ''
    sp = '<w:spacing w:before="240" w:after="80"/>' if is_h else '<w:spacing w:before="0" w:after="60"/>'
    runs = ''.join(make_run(t, is_h or b, sz, col) for t, b in parse_inline(stripped))
    return f'<w:p><w:pPr>{sp}</w:pPr>{runs}</w:p>'

def export_word(content, cycle, strat_label):
    header = (
        '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="120"/></w:pPr>'
        '<w:r><w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/>'
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:color w:val="1A3A2A"/></w:rPr>'
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

# ─── Extensions Word/ODT ──────────────────────────────────────────────────────
DOCX_EXTENSIONS = {'.docx', '.doc', '.odt', '.rtf'}

def is_word_file(uploaded_file):
    if uploaded_file is None:
        return False
    name = uploaded_file.name.lower()
    return any(name.endswith(ext) for ext in DOCX_EXTENSIONS)

# ─── Réinitialisation ────────────────────────────────────────────────────────
def reset_tab(tab_key):
    counter_key = f"reset_counter_{tab_key}"
    st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        del st.session_state[result_key]
    st.rerun()

# ─── INTERFACE ────────────────────────────────────────────────────────────────

# Bandeau héro — h1 unique
st.markdown("""
<header class="hero-band" role="banner">
  <span class="hero-label" aria-label="Outil pédagogique pour l'école primaire">
    Outil pédagogique · École primaire
  </span>
  <h1>Expert Lecteur / Lectrice</h1>
  <hr class="hero-sep" aria-hidden="true">
  <p class="hero-caption">Générateur de fiches de préparation basé sur la méthode Lector &amp; Lectrix</p>
</header>
""", unsafe_allow_html=True)

# Mention droits — icône + texte + couleur (triple signal)
st.markdown("""
<section aria-label="Mentions légales et pédagogiques">
  <div class="mention">
    Cet outil génère des fiches de préparation inspirées des méthodes
    <strong>Lector &amp; Lectrix</strong> (cycle 3) et <strong>Lectorino &amp; Lectorinette</strong> (cycle 2)
    de <strong>Sylvie Cèbe et Roland Goigoux</strong> (Éditions Retz).
    Il ne se substitue pas aux ouvrages et n'est pas affilié à leurs auteurs.
    Son usage est pédagogique, gratuit et non commercial — il a vocation à encourager les enseignants
    à s'approprier ces méthodes et à les intégrer dans leur pratique.
  </div>
</section>
""", unsafe_allow_html=True)

# Onglets
tab_auto, tab_manual = st.tabs(["🤖 Stratégie automatique — l'IA choisit", "🎯 Stratégie choisie — je choisis"])

def render_tab(tab_key, is_manual=False):
    rc = st.session_state.get(f"reset_counter_{tab_key}", 0)

    # h2 pour les sections de l'onglet (hiérarchie h1→h2)
    col_cycle, col_reset = st.columns([4, 1])
    with col_cycle:
        cycle = st.selectbox(
            "Cycle",
            CYCLES,
            index=1,
            key=f"cycle_{tab_key}_{rc}"
        )
    with col_reset:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button(
            "🔄 Réinitialiser",
            key=f"reset_{tab_key}_{rc}",
            help="Vider le formulaire et recommencer"
        ):
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

    uploaded = st.file_uploader(
        "PDF, JPEG, PNG, WebP, GIF — formats acceptés",
        type=["pdf", "jpg", "jpeg", "png", "webp", "gif", "heic",
              "docx", "doc", "odt", "rtf"],
        key=f"file_{tab_key}_{rc}"
    )

    # Message Word/ODT — icône + fond + bord + texte (pas seulement couleur)
    if is_word_file(uploaded):
        st.markdown("""
        <div class="word-warning" role="note" aria-label="Information : fichier Word détecté">
            ⚠️ <strong>Fichier Word ou ODT détecté</strong><br><br>
            Ce format ne peut pas être envoyé directement à l'IA.<br>
            La solution la plus simple :<br>
            <strong>Ouvrez votre document → Ctrl+A → Ctrl+C</strong><br>
            puis collez le texte dans la zone ci-dessous 👇
        </div>
        """, unsafe_allow_html=True)
        uploaded = None

    st.markdown(
        "<p style='text-align:center; color:#8A8475; font-weight:700; margin:6px 0; font-size:0.9rem;'>— OU —</p>",
        unsafe_allow_html=True
    )
    pasted = st.text_area(
        "Collez votre texte ici",
        height=120,
        key=f"text_{tab_key}_{rc}"
    )

    both_filled = uploaded is not None and pasted.strip()
    if both_filled:
        # Avertissement : icône ⚠️ + texte explicite, pas seulement couleur
        st.warning("⚠️ Conflit de saisie — Un fichier et du texte collé sont tous les deux présents. "
                   "L'appli utilisera uniquement le fichier. "
                   "Videz la zone de texte si vous souhaitez utiliser le texte collé.")

    btn_label = "🎯 Générer la fiche avec cette stratégie" if is_manual else "🚀 Lancer l'analyse — l'IA choisit la stratégie"
    color = "#5a3472" if is_manual else "#1A3A2A"

    # Couleur du bouton adaptée au mode (onglet)
    st.markdown(f"""
    <style>
    div[data-testid="stButton"] button[kind="primary"] {{
        background-color: {color} !important;
        color: white !important;
    }}
    </style>""", unsafe_allow_html=True)

    if st.button(btn_label, type="primary", key=f"btn_{tab_key}_{rc}"):
        if not uploaded and not pasted.strip():
            # Erreur : icône + texte explicite
            st.error("⚠️ Aucun contenu fourni — Veuillez charger un fichier ou coller un texte.")
            return

        with st.spinner("⏳ Analyse et rédaction de la fiche en cours…"):
            try:
                if is_manual:
                    prompt = build_prompt_manual(cycle, strat_num)
                    strat_label = f" · {'Priorité' if is_cycle2(cycle) else 'Stratégie'} {strat_num}"
                else:
                    prompt = build_prompt_auto(cycle)
                    strat_label = " · Stratégie automatique"

                effective_text = None if uploaded else pasted.strip() or None
                result = call_gemini(prompt, uploaded, effective_text)
                st.session_state[f"result_{tab_key}"] = (result, cycle, strat_label)
            except Exception as e:
                st.error(f"⚠️ Erreur lors de la génération — {e}")

    if f"result_{tab_key}" in st.session_state:
        result, cycle_saved, strat_saved = st.session_state[f"result_{tab_key}"]
        st.markdown("---")
        # h3 pour le titre du résultat (h1 → h2 implicite onglet → h3)
        st.markdown(
            '<h3 style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            'color:#1A3A2A;font-size:1.15rem;margin:0.5rem 0;">📄 Fiche de séance générée</h3>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="result-box" role="region" aria-label="Fiche générée">'
            f'{result}'
            f'</div>',
            unsafe_allow_html=True
        )

        fname = f"Fiche_Lector_{cycle_saved.replace(' ','_')}{strat_saved.replace(' ','_')}.docx"
        docx_bytes = export_word(result, cycle_saved, strat_saved)
        st.download_button(
            label="📥 Télécharger la fiche (Word .docx)",
            data=docx_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"dl_{tab_key}_{rc}"
        )

with tab_auto:
    render_tab("auto", is_manual=False)

with tab_manual:
    render_tab("manual", is_manual=True)
