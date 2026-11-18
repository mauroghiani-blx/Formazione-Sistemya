#!/usr/bin/env python3
"""
ispeziona_agenti.py – che cosa leggono gli agenti di coding in una cartella di progetto.

Per Claude Code, Codex e GitHub Copilot elenca, in ordine di caricamento, i file di
istruzioni, impostazioni, skill, agenti, comandi, hook e server MCP che l'agente legge
quando lavora nella cartella indicata, e mostra che cosa c'è dentro:

  - vista GERARCHICA: file per file, con sezioni e regole;
  - vista per ARGOMENTI: le regole raggruppate per tema, con duplicati
    (e, con --semantico, conflitti e lacune trovati da Claude Code).

Solo libreria standard di Python (3.11+). Funziona su Windows, Linux e macOS.

Uso:
  python ispeziona_agenti.py [cartella] [--html report.html] [--semantico]
                             [--agenti claude,codex,copilot] [--tutti]

I percorsi seguono la documentazione ufficiale (novembre 2026):
  Claude Code  https://code.claude.com/docs/en/settings.md, memory.md, skills.md, mcp.md
  Codex        https://developers.openai.com/codex
  Copilot      https://docs.github.com/copilot, https://code.visualstudio.com/docs/copilot
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None

SISTEMA = platform.system()          # 'Windows', 'Linux', 'Darwin'
HOME = Path.home()
CARTELLE_DA_SALTARE = {'.git', 'node_modules', 'bin', 'obj', 'dist', 'build', '.venv', 'venv',
                       '__pycache__', 'packages', '.vs', '.idea', 'target', '.next', 'coverage'}


# --------------------------------------------------------------------------- modello

@dataclass
class Voce:
    agente: str          # Claude Code, Codex, Copilot
    categoria: str       # Istruzioni, Impostazioni, Skill, Agenti, Comandi, MCP, Hook, Plugin, Memoria, Altro
    livello: str         # gestito, utente, progetto, locale, cartella superiore, sottocartella, importato…
    percorso: Path
    quando: str = 'all’avvio'
    nota: str = ''
    figli: list = field(default_factory=list)
    analisi: dict = field(default_factory=dict)

    @property
    def esiste(self) -> bool:
        return self.percorso.exists()


def leggi(p: Path) -> str:
    try:
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        return f'<<impossibile leggere: {e}>>'


def corto(p: Path) -> str:
    try:
        return '~' + os.sep + str(p.relative_to(HOME))
    except ValueError:
        return str(p)


def token_stimati(testo: str) -> int:
    return max(1, len(testo) // 4)


# --------------------------------------------------------------------------- analisi Markdown

FRONTMATTER = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.S)


def frontmatter(testo: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(testo)
    if not m:
        return {}, testo
    campi, ultima = {}, None
    for riga in m.group(1).splitlines():
        if ':' in riga and not riga.startswith((' ', '\t', '-')):
            k, v = riga.split(':', 1)
            ultima = k.strip()
            campi[ultima] = v.strip().strip('"\'')
        elif ultima and riga.strip().startswith('- '):          # lista YAML sotto la chiave
            voce = riga.strip()[2:].strip().strip('"\'')
            campi[ultima] = f'{campi[ultima]}, {voce}' if campi[ultima] else voce
    return campi, testo[m.end():]


def analizza_markdown(testo: str) -> dict:
    """Albero di sezioni: ogni nodo ha titolo, livello, voci (regole/testo), codice e figli."""
    fm, corpo = frontmatter(testo)
    radice = {'titolo': '', 'livello': 0, 'voci': [], 'codice': [], 'figli': []}
    pila = [radice]
    in_codice, blocco, paragrafo = False, [], False
    for riga in corpo.splitlines():
        s = riga.strip()
        e_punto = bool(re.match(r'^([-*+]|\d+[.)])\s', s))
        if s.startswith('```') or s.startswith('~~~'):
            if in_codice:
                pila[-1]['codice'].append('\n'.join(blocco))
                blocco = []
            in_codice = not in_codice
            continue
        if in_codice:
            blocco.append(riga)
            continue
        if s.startswith(('```', '~~~')):
            continue
        m = re.match(r'^(#{1,6})\s+(.*)', s)
        if m:
            liv = len(m.group(1))
            nodo = {'titolo': m.group(2).strip(), 'livello': liv, 'voci': [], 'codice': [], 'figli': []}
            while pila[-1]['livello'] >= liv:
                pila.pop()
            pila[-1]['figli'].append(nodo)
            pila.append(nodo)
            paragrafo = False
            continue
        if not s or set(s) <= set('-|: '):
            paragrafo = False
            continue
        testo_voce = re.sub(r'^([-*+]|\d+[.)])\s+', '', s)
        if s.startswith('|'):
            testo_voce = ' · '.join(c.strip() for c in s.strip('|').split('|') if c.strip())
        elif not e_punto and pila[-1]['voci'] and (paragrafo or riga.startswith((' ', '\t'))):
            pila[-1]['voci'][-1] += ' ' + s          # continuazione della voce precedente
            continue
        pila[-1]['voci'].append(testo_voce)
        paragrafo = not s.startswith('|')
    if in_codice and blocco:
        pila[-1]['codice'].append('\n'.join(blocco))
    return {'frontmatter': fm, 'sezioni': radice, 'token': token_stimati(testo)}


def import_claude(testo: str) -> list[str]:
    """Riferimenti @percorso di CLAUDE.md, esclusi blocchi di codice e `code span`."""
    trovati, in_codice = [], False
    for riga in testo.splitlines():
        if riga.strip().startswith(('```', '~~~')):
            in_codice = not in_codice
            continue
        if in_codice:
            continue
        riga = re.sub(r'`[^`]*`', '', riga)
        for m in re.finditer(r'(?:^|\s)@((?:\\ |[^\s])+)', riga):
            rif = m.group(1).replace('\\ ', ' ').rstrip('.,;:)')
            if '/' in rif or rif.endswith('.md') or rif.startswith('~'):
                trovati.append(rif)
    return trovati


# --------------------------------------------------------------------------- analisi JSON / TOML

def leggi_json(p: Path) -> tuple[dict | None, str]:
    testo = leggi(p)
    try:
        return json.loads(testo), ''
    except json.JSONDecodeError:
        # JSONC (VS Code): toglie commenti e virgole finali
        pulito = re.sub(r'//[^\n]*|/\*.*?\*/', '', testo, flags=re.S)
        pulito = re.sub(r',(\s*[}\]])', r'\1', pulito)
        try:
            return json.loads(pulito), ''
        except json.JSONDecodeError as e:
            return None, f'JSON non valido: {e}'


def leggi_toml(p: Path) -> tuple[dict | None, str]:
    if tomllib is None:
        return None, 'serve Python 3.11+ per leggere i file TOML'
    try:
        return tomllib.loads(leggi(p)), ''
    except tomllib.TOMLDecodeError as e:
        return None, f'TOML non valido: {e}'


SEGRETO = re.compile(r'(key|token|secret|password|pwd|auth)', re.I)


def maschera(chiave: str, valore) -> str:
    if SEGRETO.search(chiave):
        return '***'
    testo = json.dumps(valore, ensure_ascii=False) if not isinstance(valore, str) else valore
    return testo if len(testo) <= 160 else testo[:157] + '…'


def riassumi_impostazioni(dati: dict) -> list[str]:
    """Le chiavi principali di un file di impostazioni, una riga ciascuna."""
    righe = []
    for k, v in dati.items():
        if k == 'permissions' and isinstance(v, dict):
            for tipo in ('allow', 'ask', 'deny'):
                for regola in v.get(tipo, []) or []:
                    righe.append(f'permessi.{tipo}: {regola}')
            for k2, v2 in v.items():
                if k2 not in ('allow', 'ask', 'deny'):
                    righe.append(f'permessi.{k2}: {maschera(k2, v2)}')
        elif k == 'hooks' and isinstance(v, dict):
            for evento, gruppi in v.items():
                for g in gruppi or []:
                    matcher = g.get('matcher', '*') if isinstance(g, dict) else '*'
                    for h in (g.get('hooks', []) if isinstance(g, dict) else []):
                        cosa = h.get('command') or h.get('url') or h.get('prompt') or h.get('type')
                        righe.append(f'hook {evento} [{matcher}]: {maschera("cmd", cosa)}')
        elif k == 'env' and isinstance(v, dict):
            for nome, val in v.items():
                righe.append(f'env {nome} = {maschera(nome, val)}')
        elif k in ('mcpServers', 'mcp_servers', 'servers') and isinstance(v, dict):
            for nome, conf in v.items():
                cmd = conf.get('command') or conf.get('url') or conf.get('type', '') if isinstance(conf, dict) else conf
                righe.append(f'MCP {nome}: {maschera("cmd", cmd)}')
        elif k == 'projects' and isinstance(v, dict):
            righe.append(f'projects: {len(v)} progetti registrati')
        elif isinstance(v, dict) and len(json.dumps(v)) > 160:
            righe.append(f'{k}: {{{", ".join(list(v)[:8])}{"…" if len(v) > 8 else ""}}}')
        else:
            righe.append(f'{k}: {maschera(k, v)}')
    return righe


# --------------------------------------------------------------------------- utilità percorsi

def antenati(cartella: Path) -> list[Path]:
    """Dalla radice del disco fino alla cartella (inclusa)."""
    return list(reversed([cartella, *cartella.parents]))


def radice_git(cartella: Path) -> Path | None:
    for d in [cartella, *cartella.parents]:
        if (d / '.git').exists():
            return d
    return None


def sottocartelle(cartella: Path, profondita: int):
    """Tutte le sottocartelle fino a 'profondita', saltando build, dipendenze e cartelle nascoste."""
    base = len(cartella.parts)
    for radice, dirs, _ in os.walk(cartella):
        r = Path(radice)
        dirs[:] = [d for d in dirs if d not in CARTELLE_DA_SALTARE and not (d.startswith('.') and d not in ('.claude', '.github', '.codex', '.agents'))]
        if len(r.parts) - base >= profondita:
            dirs[:] = []
        if r != cartella:
            yield r


def file_md(cartella: Path, schema: str = '*.md') -> list[Path]:
    return sorted(cartella.glob(schema)) if cartella.is_dir() else []


def cartelle_gestite() -> dict[str, Path]:
    if SISTEMA == 'Windows':
        return {'settings': Path(r'C:\ProgramData\ClaudeCode'), 'claude_md': Path(r'C:\Program Files\ClaudeCode')}
    if SISTEMA == 'Darwin':
        p = Path('/Library/Application Support/ClaudeCode')
        return {'settings': p, 'claude_md': p}
    return {'settings': Path('/etc/claude-code'), 'claude_md': Path('/etc/claude-code')}


# --------------------------------------------------------------------------- Claude Code

def claude_code(progetto: Path, profondita: int) -> list[Voce]:
    A = 'Claude Code'
    cfg = Path(os.environ.get('CLAUDE_CONFIG_DIR', HOME / '.claude'))
    gest = cartelle_gestite()
    voci: list[Voce] = []

    # Istruzioni (ordine di caricamento)
    voci.append(Voce(A, 'Istruzioni', 'gestito', gest['claude_md'] / 'CLAUDE.md', nota='imposto dall’IT, non si può escludere'))
    if SISTEMA == 'Windows':
        voci.append(Voce(A, 'Istruzioni', 'gestito', gest['settings'] / 'CLAUDE.md', nota='percorso alternativo usato da alcune installazioni'))
    voci.append(Voce(A, 'Istruzioni', 'utente', cfg / 'CLAUDE.md'))
    for r in file_md(cfg / 'rules', '**/*.md'):
        voci.append(Voce(A, 'Istruzioni', 'utente – regola', r))
    trovato_claude_md = False
    for d in antenati(progetto):
        liv = 'progetto' if d == progetto else 'cartella superiore'
        for nome in ('CLAUDE.md', '.claude/CLAUDE.md', 'CLAUDE.local.md'):
            p = d / nome
            if p.exists() or d == progetto:
                livello = (liv + ' – personale') if nome == 'CLAUDE.local.md' else liv
                voci.append(Voce(A, 'Istruzioni', livello, p,
                                 nota='personale, di solito non va su git' if nome == 'CLAUDE.local.md' else ''))
                trovato_claude_md |= p.exists() and nome != 'CLAUDE.local.md'
    for d in antenati(progetto):
        if (d / 'AGENTS.md').exists():
            voci.append(Voce(A, 'Istruzioni', 'cartella superiore' if d != progetto else 'progetto', d / 'AGENTS.md',
                             quando='solo se non c’è nessun CLAUDE.md' if trovato_claude_md else 'all’avvio (nessun CLAUDE.md)',
                             nota='impostazione predefinita, si cambia da /config → Project instructions'))
    for r in file_md(progetto / '.claude' / 'rules', '**/*.md'):
        fm, _ = frontmatter(leggi(r))
        voci.append(Voce(A, 'Istruzioni', 'progetto – regola', r,
                         quando=f'su richiesta, per i file {fm["paths"]}' if fm.get('paths') else 'all’avvio'))
    for d in sottocartelle(progetto, profondita):
        for nome in ('CLAUDE.md', 'CLAUDE.local.md', 'AGENTS.md'):
            if (d / nome).exists() and d.name != '.claude':
                voci.append(Voce(A, 'Istruzioni', 'sottocartella', d / nome,
                                 quando='su richiesta, quando lavora in quella cartella'))

    # Memoria automatica
    radice = radice_git(progetto) or progetto
    nome_progetto = os.environ.get('CLAUDE_CODE_PROJECT_DIR_NAME') or re.sub(r'[^A-Za-z0-9]', '-', str(radice))
    memoria = cfg / 'projects' / nome_progetto / 'memory' / 'MEMORY.md'
    voci.append(Voce(A, 'Memoria', 'automatica', memoria, quando='all’avvio (prime 200 righe / 25 KB)',
                     nota='indice delle memorie; i singoli file si leggono su richiesta'))

    # Impostazioni (dalla più forte alla più debole)
    voci.append(Voce(A, 'Impostazioni', 'gestito', gest['settings'] / 'managed-settings.json', nota='vince su tutto'))
    voci.append(Voce(A, 'Impostazioni', 'locale', progetto / '.claude' / 'settings.local.json', nota='personale, per questo progetto'))
    voci.append(Voce(A, 'Impostazioni', 'progetto', progetto / '.claude' / 'settings.json', nota='condiviso su git'))
    voci.append(Voce(A, 'Impostazioni', 'utente', cfg / 'settings.json'))
    if (cfg / 'settings.local.json').exists():
        voci.append(Voce(A, 'Impostazioni', 'utente', cfg / 'settings.local.json', nota='presente, non citato nella documentazione'))
    voci.append(Voce(A, 'Impostazioni', 'stato globale', HOME / '.claude.json', nota='scritto da Claude Code: account, MCP, progetti'))
    voci.append(Voce(A, 'Impostazioni', 'utente', cfg / 'keybindings.json', nota='scorciatoie da tastiera'))

    # Estensioni
    for base, liv in ((cfg, 'utente'), (progetto / '.claude', 'progetto')):
        for s in sorted((base / 'skills').glob('**/SKILL.md')) if (base / 'skills').is_dir() else []:
            voci.append(Voce(A, 'Skill', liv, s, quando='descrizione all’avvio, contenuto quando serve'))
        for a in file_md(base / 'agents', '**/*.md'):
            voci.append(Voce(A, 'Agenti', liv, a, quando='descrizione all’avvio, contenuto quando viene usato'))
        for c in file_md(base / 'commands', '**/*.md'):
            voci.append(Voce(A, 'Comandi', liv, c, quando='quando si digita /' + c.stem))
        for o in file_md(base / 'output-styles'):
            voci.append(Voce(A, 'Altro', liv + ' – stile di output', o, quando='se selezionato'))
        for w in sorted((base / 'workflows').glob('**/*.js')) if (base / 'workflows').is_dir() else []:
            voci.append(Voce(A, 'Altro', liv + ' – workflow', w, quando='quando viene lanciato'))
    for d in sottocartelle(progetto, profondita):
        if d.name == 'skills' and d.parent.name == '.claude' and d.parent.parent != progetto:
            for s in sorted(d.glob('*/SKILL.md')):
                voci.append(Voce(A, 'Skill', 'sottocartella', s, quando='quando lavora in quella cartella'))

    # Plugin
    plugin = cfg / 'plugins'
    registro = plugin / 'installed_plugins.json'
    voci.append(Voce(A, 'Plugin', 'utente', registro, nota='elenco dei plugin installati'))
    installati = []                    # le cartelle in plugins/marketplaces sono solo il catalogo
    if registro.exists():
        dati, _ = leggi_json(registro)
        elenco = (dati or {}).get('plugins', dati or {})
        for nome, istanze in (elenco.items() if isinstance(elenco, dict) else []):
            for ist in istanze if isinstance(istanze, list) else [istanze]:
                if isinstance(ist, dict) and ist.get('installPath'):
                    installati.append((nome, Path(ist['installPath'])))
    for nome, base in installati:
        for s in sorted(base.glob('skills/*/SKILL.md')):
            voci.append(Voce(A, 'Skill', f'plugin {nome}', s, quando='descrizione all’avvio, contenuto quando serve'))
        for a in sorted(base.glob('agents/*.md')):
            voci.append(Voce(A, 'Agenti', f'plugin {nome}', a, quando='descrizione all’avvio'))
        for c in sorted(base.glob('commands/**/*.md')):
            voci.append(Voce(A, 'Comandi', f'plugin {nome}', c, quando='quando si digita /' + c.stem))

    # MCP
    voci.append(Voce(A, 'MCP', 'gestito', gest['settings'] / 'managed-mcp.json'))
    voci.append(Voce(A, 'MCP', 'progetto', progetto / '.mcp.json', nota='condiviso su git'))
    return voci


# --------------------------------------------------------------------------- Codex

def codex(progetto: Path, profondita: int) -> list[Voce]:
    A = 'Codex'
    home = Path(os.environ.get('CODEX_HOME', HOME / '.codex'))
    radice = radice_git(progetto) or progetto
    voci: list[Voce] = []

    utente_cfg, _ = leggi_toml(home / 'config.toml') if (home / 'config.toml').exists() else ({}, '')
    utente_cfg = utente_cfg or {}
    alternativi = utente_cfg.get('project_doc_fallback_filenames', []) or []
    fidato = (utente_cfg.get('projects', {}).get(str(radice), {}) or {}).get('trust_level') == 'trusted'

    # Istruzioni: globale, poi dalla radice del repository fino alla cartella
    override = home / 'AGENTS.override.md'
    if override.exists():
        voci.append(Voce(A, 'Istruzioni', 'utente', override, nota='sostituisce ~/.codex/AGENTS.md'))
    else:
        voci.append(Voce(A, 'Istruzioni', 'utente', home / 'AGENTS.md'))
    catena = [d for d in antenati(progetto) if d == radice or radice in d.parents]
    for d in catena:
        livello = 'progetto' if d == progetto else ('radice repository' if d == radice else 'cartella intermedia')
        scelto = next((d / n for n in ('AGENTS.override.md', 'AGENTS.md', *alternativi) if (d / n).exists()), None)
        voci.append(Voce(A, 'Istruzioni', livello, scelto or d / 'AGENTS.md',
                         nota='un solo file per cartella; i più vicini alla cartella di lavoro vengono dopo e prevalgono'))
    for d in sottocartelle(progetto, profondita):
        if (d / 'AGENTS.md').exists():
            voci.append(Voce(A, 'Istruzioni', 'sottocartella', d / 'AGENTS.md',
                             quando='solo se Codex parte da quella cartella (o sotto)'))

    # Impostazioni (dalla più forte alla più debole)
    for d in reversed(catena):
        p = d / '.codex' / 'config.toml'
        if p.exists() or d == progetto:
            voci.append(Voce(A, 'Impostazioni', 'progetto', p,
                             quando='all’avvio' if fidato else 'solo se il progetto è “trusted”',
                             nota='il più vicino alla cartella di lavoro vince'))
    for prof in sorted(home.glob('*.config.toml')):
        voci.append(Voce(A, 'Impostazioni', 'profilo', prof, quando=f'con --profile {prof.name.split(".")[0]}'))
    voci.append(Voce(A, 'Impostazioni', 'utente', home / 'config.toml', nota='contiene anche i server MCP e i progetti fidati'))
    if SISTEMA != 'Windows':
        voci.append(Voce(A, 'Impostazioni', 'sistema', Path('/etc/codex/config.toml')))

    # Skill: .agents/skills dalla cartella fino alla radice, poi utente e amministratore
    for d in reversed(catena):
        for s in sorted((d / '.agents' / 'skills').glob('*/SKILL.md')):
            voci.append(Voce(A, 'Skill', 'progetto', s, quando='descrizione all’avvio, contenuto quando serve'))
    for base, liv in ((HOME / '.agents' / 'skills', 'utente'), (Path('/etc/codex/skills'), 'amministratore')):
        for s in sorted(base.glob('*/SKILL.md')) if base.is_dir() else []:
            voci.append(Voce(A, 'Skill', liv, s, quando='descrizione all’avvio, contenuto quando serve'))
    for base in (home / 'skills', progetto / '.codex' / 'skills'):
        for s in sorted(base.glob('*/SKILL.md')) if base.is_dir() else []:
            voci.append(Voce(A, 'Skill', 'vecchio percorso', s, nota='percorso non più documentato: spostare in .agents/skills'))

    # Agenti personalizzati in formato TOML
    for base, liv in ((progetto / '.codex' / 'agents', 'progetto'), (home / 'agents', 'utente')):
        for a in sorted(base.glob('*.toml')) if base.is_dir() else []:
            voci.append(Voce(A, 'Agenti', liv, a, quando='quando viene usato'))

    # Prompt personalizzati (deprecati, sostituiti dalle skill)
    for c in file_md(home / 'prompts'):
        voci.append(Voce(A, 'Comandi', 'utente', c, quando=f'quando si digita /prompts:{c.stem}', nota='deprecato: usare le skill'))
    return voci


# --------------------------------------------------------------------------- GitHub Copilot

def profilo_vscode() -> Path:
    if SISTEMA == 'Windows':
        return Path(os.environ.get('APPDATA', HOME / 'AppData' / 'Roaming')) / 'Code' / 'User'
    if SISTEMA == 'Darwin':
        return HOME / 'Library' / 'Application Support' / 'Code' / 'User'
    return Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'Code' / 'User'


def copilot(progetto: Path, profondita: int) -> list[Voce]:
    A = 'Copilot'
    home = Path(os.environ.get('COPILOT_HOME', HOME / '.copilot'))
    radice = radice_git(progetto) or progetto
    gh = radice / '.github'
    vsc = profilo_vscode()
    voci: list[Voce] = []
    catena = [d for d in antenati(progetto) if d == radice or radice in d.parents]

    # Istruzioni (Copilot le unisce tutte, senza un ordine di precedenza)
    voci.append(Voce(A, 'Istruzioni', 'utente', home / 'copilot-instructions.md'))
    for f in sorted((home / 'instructions').glob('**/*.instructions.md')) if (home / 'instructions').is_dir() else []:
        voci.append(Voce(A, 'Istruzioni', 'utente', f, quando=applica_a(f)))
    voci.append(Voce(A, 'Istruzioni', 'repository', gh / 'copilot-instructions.md'))
    for f in sorted((gh / 'instructions').glob('**/*.instructions.md')) if (gh / 'instructions').is_dir() else []:
        voci.append(Voce(A, 'Istruzioni', 'repository', f, quando=applica_a(f)))
    for d in catena:
        livello = 'repository' if d == radice else ('progetto' if d == progetto else 'cartella intermedia')
        for nome in ('AGENTS.md', 'CLAUDE.md', '.claude/CLAUDE.md', 'GEMINI.md'):
            p = d / nome
            if p.exists() or (nome == 'AGENTS.md' and d == radice):
                voci.append(Voce(A, 'Istruzioni', livello, p,
                                 nota='' if nome == 'AGENTS.md' else 'letto da Copilot CLI'))
    for d in sottocartelle(progetto, profondita):
        if (d / 'AGENTS.md').exists():
            voci.append(Voce(A, 'Istruzioni', 'sottocartella', d / 'AGENTS.md', quando='quando lavora su file di quella cartella'))
    for extra in filter(None, os.environ.get('COPILOT_CUSTOM_INSTRUCTIONS_DIRS', '').split(',')):
        voci.append(Voce(A, 'Istruzioni', 'cartella aggiuntiva', Path(extra.strip()) / 'AGENTS.md',
                         nota='da COPILOT_CUSTOM_INSTRUCTIONS_DIRS'))

    # Agenti personalizzati
    for base, liv in ((gh / 'agents', 'repository'), (radice / '.claude' / 'agents', 'repository (formato Claude)'),
                      (home / 'agents', 'utente')):
        for a in sorted(base.glob('**/*.md')) if base.is_dir() else []:
            voci.append(Voce(A, 'Agenti', liv, a, quando='quando viene scelto'))
    for m in sorted((gh / 'chatmodes').glob('*.chatmode.md')) if (gh / 'chatmodes').is_dir() else []:
        voci.append(Voce(A, 'Agenti', 'repository', m, nota='vecchio formato: rinominare in .agent.md e spostare in .github/agents'))

    # Skill (in caso di nomi uguali vince la prima)
    for base, liv in ((gh / 'skills', 'repository'), (radice / '.agents' / 'skills', 'repository'),
                      (radice / '.claude' / 'skills', 'repository'), (home / 'skills', 'utente'),
                      (HOME / '.agents' / 'skills', 'utente')):
        for s in sorted(base.glob('*/SKILL.md')) if base.is_dir() else []:
            voci.append(Voce(A, 'Skill', liv, s, quando='descrizione all’avvio, contenuto quando serve'))

    # Prompt file (solo VS Code “Local”, deprecati)
    for c in sorted((gh / 'prompts').glob('*.prompt.md')) if (gh / 'prompts').is_dir() else []:
        voci.append(Voce(A, 'Comandi', 'repository', c, quando='quando si digita /' + c.name[:-10],
                         nota='solo VS Code “Local”, deprecato: convertire in skill'))

    # Impostazioni
    voci.append(Voce(A, 'Impostazioni', 'locale', gh / 'copilot' / 'settings.local.json'))
    voci.append(Voce(A, 'Impostazioni', 'repository', gh / 'copilot' / 'settings.json'))
    voci.append(Voce(A, 'Impostazioni', 'utente', home / 'settings.json', nota='Copilot CLI'))
    voci.append(Voce(A, 'Impostazioni', 'stato', home / 'config.json', nota='solo stato: accesso, plugin, cartelle fidate'))
    voci.append(Voce(A, 'Impostazioni', 'VS Code', vsc / 'settings.json', nota='mostrate solo le chiavi chat.* e github.copilot.*'))

    # MCP
    for d in reversed(catena):
        for nome in ('.mcp.json', '.github/mcp.json'):
            if (d / nome).exists() or (d == radice and nome == '.mcp.json'):
                voci.append(Voce(A, 'MCP', 'repository', d / nome, quando='solo se la cartella è fidata'))
    voci.append(Voce(A, 'MCP', 'utente', home / 'mcp-config.json'))
    voci.append(Voce(A, 'MCP', 'VS Code “Local”', radice / '.vscode' / 'mcp.json', nota='deprecato, non letto da Copilot CLI'))
    voci.append(Voce(A, 'MCP', 'VS Code “Local”', vsc / 'mcp.json', nota='deprecato'))
    return voci


def applica_a(f: Path) -> str:
    fm, _ = frontmatter(leggi(f))
    return f'per i file {fm["applyTo"]}' if fm.get('applyTo') else 'sempre'


# --------------------------------------------------------------------------- analisi dei contenuti

def analizza(voce: Voce, avvisi: list[str], profondita_import: int = 0) -> None:
    if not voce.esiste or voce.percorso.is_dir():
        return
    p = voce.percorso
    testo = leggi(p)
    nome = p.name.lower()
    if nome.endswith('.md'):
        voce.analisi = analizza_markdown(testo)
        fm = voce.analisi['frontmatter']
        righe = testo.count('\n') + 1
        if voce.categoria in ('Skill', 'Agenti') and not fm.get('description'):
            avvisi.append(f'{voce.agente}: {p} non ha “description” nel frontmatter: l’agente non sa quando usarlo.')
        if voce.categoria == 'Istruzioni' and righe > 200:
            quando = 'a ogni sessione' if voce.quando.startswith('all') else voce.quando
            avvisi.append(f'{voce.agente}: {p} ha {righe} righe (~{voce.analisi["token"]} token, caricati {quando}).')
        if voce.agente == 'Claude Code' and voce.categoria in ('Istruzioni', 'Memoria'):
            for rif in import_claude(testo):
                dest = Path(os.path.expanduser(rif)) if rif.startswith('~') else (p.parent / rif)
                figlio = Voce(voce.agente, voce.categoria, 'importato', dest.resolve(), quando=voce.quando,
                              nota=f'@{rif} in {p.name}')
                if not figlio.esiste:
                    avvisi.append(f'Claude Code: import rotto @{rif} in {p}')
                elif profondita_import < 4:
                    analizza(figlio, avvisi, profondita_import + 1)
                voce.figli.append(figlio)
    elif nome.endswith('.json'):
        dati, errore = leggi_json(p)
        if errore:
            avvisi.append(f'{voce.agente}: {p}: {errore}')
            return
        if voce.livello == 'VS Code':
            dati = {k: v for k, v in dati.items() if k.startswith(('chat.', 'github.copilot'))}
        if p.name == '.claude.json':
            progetti = dati.get('projects', {})
            dati = {'mcpServers': dati.get('mcpServers', {}), 'projects': progetti}
        if p.name == 'installed_plugins.json':
            elenco = dati.get('plugins', dati)
            dati = {f'plugin {k}': (v[0].get('version', '') if isinstance(v, list) and v and isinstance(v[0], dict) else '')
                    for k, v in (elenco.items() if isinstance(elenco, dict) else [])}
        voce.analisi = {'righe': riassumi_impostazioni(dati), 'dati': dati}
    elif nome.endswith('.toml'):
        dati, errore = leggi_toml(p)
        if errore:
            avvisi.append(f'{voce.agente}: {p}: {errore}')
            return
        voce.analisi = {'righe': riassumi_impostazioni(dati), 'dati': dati}
    else:
        voce.analisi = {'righe': [f'{len(testo.splitlines())} righe']}


def impostazioni_effettive(voci: list[Voce]) -> list[str]:
    """Claude Code: per ogni chiave, quale file vince (le liste si sommano)."""
    ordine = [v for v in voci if v.agente == 'Claude Code' and v.categoria == 'Impostazioni'
              and v.esiste and 'dati' in v.analisi and v.percorso.name != '.claude.json'
              and v.percorso.name != 'keybindings.json']
    chiavi: dict[str, list[tuple[Voce, object]]] = {}
    for v in ordine:                                         # già dalla più forte alla più debole
        for k, val in v.analisi['dati'].items():
            chiavi.setdefault(k, []).append((v, val))
    righe = []
    for k, fonti in chiavi.items():
        if k in ('permissions', 'env', 'hooks', 'enabledPlugins'):
            righe.append(f'{k}: unione di {", ".join(f.livello for f, _ in fonti)}')
        elif len(fonti) > 1:
            vince, val = fonti[0]
            perdenti = ', '.join(f'{f.livello}={maschera(k, x)}' for f, x in fonti[1:])
            righe.append(f'{k} = {maschera(k, val)}  (vince {vince.livello}; ignorati: {perdenti})')
    return righe


# --------------------------------------------------------------------------- vista per argomenti

ARGOMENTI = {
    'Build e test': ['build', 'compil', 'test', 'dotnet', 'npm ', 'pytest', 'msbuild', 'gradle', 'maven', 'pipeline'],
    'Git e PR': ['git', 'commit', 'branch', 'pull request', ' pr ', 'merge', 'rebase', 'push', 'review', 'worktree'],
    'Stile del codice': ['stile', 'style', 'naming', 'nomi ', 'format', 'lint', 'convenzion', 'convention', 'indent', 'commenti'],
    'Database': ['sql', 'database', ' db', 'query', 'migration', 'stored', 'tabell', 'table', 'schema'],
    'Sicurezza e permessi': ['sicurezz', 'security', 'secret', 'password', 'credential', 'permess', 'permission', 'permessi.',
                             'allow', 'deny'],
    'Documentazione': ['documentaz', 'documentation', 'readme', 'wiki', 'changelog', 'docs'],
    'Architettura': ['architett', 'architecture', 'layer', 'modul', 'servizio', 'service', ' api', 'pattern', 'progetto'],
    'Strumenti, skill e MCP': ['mcp', 'tool', 'strument', 'skill', 'agent', 'hook', 'plugin', 'subagent'],
    'Comunicazione': ['rispond', 'risposta', 'answer', 'lingua', 'language', 'italiano', 'english', 'tono', 'tone', 'concis', 'breve'],
    'Ambiente e risorse': ['ram', 'memoria', 'disco', 'disk', 'docker', ' vm', 'ambiente', 'environment', 'env ', 'cpu', 'windows', 'linux'],
}


def regole(voce: Voce):
    """(sezione, testo) per ogni regola di un file, figli importati compresi."""
    if 'sezioni' in voce.analisi:
        def visita(nodo, percorso):
            titolo = ' › '.join(x for x in percorso if x)
            for v in nodo['voci']:
                yield titolo, v
            for f in nodo['figli']:
                yield from visita(f, percorso + [f['titolo']])
        yield from visita(voce.analisi['sezioni'], [])
    elif 'righe' in voce.analisi and voce.categoria in ('Impostazioni', 'MCP'):
        for r in voce.analisi['righe']:
            yield '', r
    for f in voce.figli:
        yield from regole(f)


def per_argomento(voci: list[Voce]):
    """Solo istruzioni, memoria e impostazioni: le skill e gli agenti sono procedure, non regole sempre attive.
    Un file letto da più agenti compare una volta sola, con tutti gli agenti che lo leggono."""
    gruppi: dict[str, list] = {a: [] for a in ARGOMENTI}
    gruppi['Altro'] = []
    visti: dict[str, list] = {}
    lettori: dict[Path, list[str]] = {}
    for v in voci:
        if v.esiste:
            lettori.setdefault(v.percorso, []).append(v.agente)
    fatti = set()
    for v in voci:
        if not v.esiste or v.categoria not in ('Istruzioni', 'Memoria', 'Impostazioni', 'MCP') or v.percorso in fatti:
            continue
        fatti.add(v.percorso)
        v.lettori = ' / '.join(dict.fromkeys(lettori[v.percorso]))
        for sezione, testo in regole(v):
            contesto = f' {sezione} {testo} '.lower()
            presi = [a for a, parole in ARGOMENTI.items() if any(p in contesto for p in parole)] or ['Altro']
            for a in presi:
                gruppi[a].append((v, sezione, testo))
            chiave = re.sub(r'[\W_]+', ' ', testo.lower()).strip()
            if len(chiave) > 25:
                visti.setdefault(chiave, []).append(v)
    duplicati = [(testo, fonti) for testo, fonti in visti.items() if len({f.percorso for f in fonti}) > 1]
    return gruppi, duplicati


# --------------------------------------------------------------------------- modalità semantica (claude -p)

SCHEMA_SEMANTICO = {
    'type': 'object',
    'properties': {
        'argomenti': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'nome': {'type': 'string'}, 'sintesi': {'type': 'string'},
            'regole': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'testo': {'type': 'string'}, 'fonti': {'type': 'array', 'items': {'type': 'string'}}}}}}}},
        'duplicati': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'descrizione': {'type': 'string'}, 'fonti': {'type': 'array', 'items': {'type': 'string'}}}}},
        'conflitti': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'descrizione': {'type': 'string'}, 'fonti': {'type': 'array', 'items': {'type': 'string'}}}}},
        'lacune': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['argomenti', 'duplicati', 'conflitti', 'lacune'],
}


def semantico(voci: list[Voce], limite_caratteri: int = 120_000) -> tuple[dict | None, str]:
    eseguibile = shutil.which('claude')
    if not eseguibile:
        return None, 'Claude Code non trovato nel PATH: installalo o togli --semantico.'
    blocchi, totale = [], 0
    for i, v in enumerate(x for x in voci if x.esiste and x.categoria in ('Istruzioni', 'Memoria', 'Skill', 'Agenti', 'Comandi', 'Impostazioni', 'MCP')):
        contenuto = '\n'.join(f'- [{s}] {t}' if s else f'- {t}' for s, t in regole(v))
        if not contenuto:
            continue
        blocco = f'### F{i} | {v.agente} | {v.categoria} | {v.livello} | {v.percorso}\n{contenuto}\n'
        if totale + len(blocco) > limite_caratteri:
            blocchi.append('(altri file omessi per lunghezza)')
            break
        blocchi.append(blocco)
        totale += len(blocco)
    prompt = (
        'Sei un revisore di configurazioni per agenti di coding (Claude Code, Codex, GitHub Copilot).\n'
        'Qui sotto ci sono le regole estratte dai file che questi agenti leggono, ognuno con un identificativo F<n>.\n'
        'Rispondi SOLO con un oggetto JSON (nessun testo prima o dopo) con queste chiavi:\n'
        '- "argomenti": raggruppa le regole per tema (build e test, git e PR, stile, database, sicurezza, '
        'documentazione, architettura, strumenti, comunicazione, ambiente, altro). Per ogni tema: "nome", '
        '"sintesi" (una frase), "regole" (testo riassunto + "fonti" con gli identificativi F<n>).\n'
        '- "duplicati": regole uguali o equivalenti in file diversi.\n'
        '- "conflitti": regole che si contraddicono, anche tra agenti diversi.\n'
        '- "lacune": temi coperti per un agente e non per un altro, o regole importanti che mancano.\n'
        'Scrivi in italiano. Non inventare regole che non ci sono.\n\n' + '\n'.join(blocchi))
    comando = [eseguibile, '-p', '--output-format', 'json', '--tools', '']
    try:
        with tempfile.TemporaryDirectory() as vuota:          # cartella vuota: niente CLAUDE.md del progetto
            r = subprocess.run(comando, input=prompt, capture_output=True, text=True, encoding='utf-8',
                               cwd=vuota, timeout=900)
    except subprocess.TimeoutExpired:
        return None, 'claude -p non ha risposto entro 15 minuti.'
    if r.returncode != 0:
        return None, f'claude -p è terminato con errore: {r.stderr.strip()[:500]}'
    try:
        risposta = json.loads(r.stdout).get('result', '')
        testo = re.sub(r'^```(?:json)?\s*|\s*```$', '', risposta.strip())
        return json.loads(testo[testo.index('{'):testo.rindex('}') + 1]), ''
    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        return None, f'risposta di claude -p non leggibile come JSON: {e}'


# --------------------------------------------------------------------------- uscita su terminale

def testo_lacuna(l) -> str:
    if isinstance(l, dict):
        fonti = ', '.join(l.get('fonti', []))
        return l.get('descrizione', str(l)) + (f'  [{fonti}]' if fonti else '')
    return str(l)


def taglia(testo: str, n: int) -> str:
    testo = ' '.join(testo.split())
    return testo if n <= 0 or len(testo) <= n else testo[:n - 1] + '…'


def stampa_sezioni(nodo, rientro: str, larghezza: int):
    for v in nodo['voci']:
        print(f'{rientro}• {taglia(v, larghezza)}')
    for c in nodo['codice']:
        print(f'{rientro}▸ codice: {taglia(c.splitlines()[0] if c else "", larghezza)}'
              f'{" (+%d righe)" % (len(c.splitlines()) - 1) if len(c.splitlines()) > 1 else ""}')
    for f in nodo['figli']:
        print(f'{rientro}{"#" * f["livello"]} {f["titolo"]}')
        stampa_sezioni(f, rientro + '   ', larghezza)


def stampa_voce(v: Voce, rientro: str, mostra_assenti: bool, larghezza: int):
    if not v.esiste:
        if mostra_assenti:
            print(f'{rientro}–  [{v.livello}] {corto(v.percorso)}')
        return
    tok = v.analisi.get('token')
    info = ', '.join(x for x in (v.quando, f'~{tok} token' if tok else '', v.nota) if x)
    print(f'{rientro}✓  [{v.livello}] {corto(v.percorso)}  ({info})')
    fm = v.analisi.get('frontmatter') or {}
    for k in ('name', 'description', 'applyTo', 'paths'):
        if fm.get(k):
            print(f'{rientro}     {k}: {taglia(fm[k], larghezza)}')
    if 'sezioni' in v.analisi:
        if DETTAGLIO:
            stampa_sezioni(v.analisi['sezioni'], rientro + '     ', larghezza)
        else:
            stampa_indice(v.analisi['sezioni'], rientro + '     ')
    righe = v.analisi.get('righe', [])
    for r in righe if DETTAGLIO else righe[:12]:
        print(f'{rientro}     · {taglia(r, larghezza)}')
    if not DETTAGLIO and len(righe) > 12:
        print(f'{rientro}     · … altre {len(righe) - 12} (usa --dettaglio)')
    for f in v.figli:
        stampa_voce(f, rientro + '     ', mostra_assenti, larghezza)


def conta(nodo) -> int:
    return len(nodo['voci']) + sum(conta(f) for f in nodo['figli'])


def stampa_indice(nodo, rientro: str):
    """Solo i titoli delle sezioni con il numero di regole: la struttura del file a colpo d'occhio."""
    for f in nodo['figli']:
        print(f'{rientro}{"#" * f["livello"]} {f["titolo"]}  ({conta(f)} regole)')
        stampa_indice(f, rientro + '   ')


DETTAGLIO = False
CATEGORIE = ['Istruzioni', 'Memoria', 'Impostazioni', 'Skill', 'Agenti', 'Comandi', 'Hook', 'MCP', 'Plugin', 'Altro']


def stampa(voci, effettive, gruppi, duplicati, sem, avvisi, args):
    for agente in dict.fromkeys(v.agente for v in voci):
        sue = [v for v in voci if v.agente == agente]
        presenti = sum(v.esiste for v in sue)
        print(f'\n{"=" * 78}\n{agente.upper()}   ({presenti} file presenti su {len(sue)} percorsi controllati)\n{"=" * 78}')
        for cat in CATEGORIE:
            elenco = [v for v in sue if v.categoria == cat]
            if not elenco or (not args.tutti and not any(v.esiste for v in elenco)):
                continue
            print(f'\n{cat}')
            for v in elenco:
                stampa_voce(v, '  ', args.tutti, args.larghezza)
        if agente == 'Claude Code' and effettive:
            print('\nImpostazioni effettive (chi vince)')
            for r in effettive:
                print(f'  · {r}')
    print(f'\n{"=" * 78}\nPER ARGOMENTO (classificazione per parole chiave)\n{"=" * 78}')
    for arg, elenco in gruppi.items():
        if elenco:
            print(f'\n{arg}  ({len(elenco)} regole)')
            if DETTAGLIO:
                for v, sezione, testo in elenco:
                    print(f'  [{v.lettori} · {v.percorso.name}] {taglia(testo, args.larghezza)}')
            else:
                file = {}
                for v, _, _ in elenco:
                    file[(v.lettori, corto(v.percorso))] = file.get((v.lettori, corto(v.percorso)), 0) + 1
                for (agente, nome), n in file.items():
                    print(f'  {n:3d}  {agente} · {nome}')
    if duplicati:
        print('\nDuplicati (stessa regola in più file)')
        for testo, fonti in duplicati:
            print(f'  “{taglia(testo, 80)}” → ' + ', '.join(sorted({str(f.percorso) for f in fonti})))
    if sem:
        print(f'\n{"=" * 78}\nANALISI SEMANTICA (claude -p)\n{"=" * 78}')
        for a in sem.get('argomenti', []):
            print(f'\n{a.get("nome")}: {a.get("sintesi", "")}')
            for r in a.get('regole', []):
                print(f'  • {taglia(r.get("testo", ""), args.larghezza)}  [{", ".join(r.get("fonti", []))}]')
        for titolo, chiave in (('Conflitti', 'conflitti'), ('Duplicati', 'duplicati')):
            if sem.get(chiave):
                print(f'\n{titolo}')
                for c in sem[chiave]:
                    print(f'  ! {c.get("descrizione")}  [{", ".join(c.get("fonti", []))}]')
        if sem.get('lacune'):
            print('\nLacune')
            for l in sem['lacune']:
                print(f'  ? {testo_lacuna(l)}')
    if avvisi:
        print(f'\n{"=" * 78}\nAVVISI\n{"=" * 78}')
        for a in avvisi:
            print(f'  ⚠ {a}')


# --------------------------------------------------------------------------- report HTML

CSS = '''
:root{--blu:#1F3A5F;--azz:#DCE6F2;--aran:#C25A00;--aran-ch:#FCE2C4;--grigio:#EDEDED;--testo:#262626;--sfondo:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--blu:#9DB8DC;--azz:#22344d;--aran:#F0A050;--aran-ch:#4a3320;--grigio:#2b2b2b;--testo:#e8e8e8;--sfondo:#161616}}
*{box-sizing:border-box}body{font-family:Verdana,sans-serif;font-size:14px;color:var(--testo);background:var(--sfondo);margin:0;padding:16px;line-height:1.5}
h1{color:var(--blu);font-size:22px;margin:0 0 4px}.sotto{color:#777;margin-bottom:16px;word-break:break-all}
.schede{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.schede button{font:inherit;padding:8px 14px;border:2px solid var(--blu);background:var(--sfondo);color:var(--blu);border-radius:6px;cursor:pointer}
.schede button.attiva{background:var(--blu);color:var(--sfondo)}.pannello{display:none}.pannello.attivo{display:block}
details{margin:4px 0 4px 8px;border-left:3px solid var(--azz);padding-left:10px}summary{cursor:pointer;padding:3px 0}
.agente>summary{font-size:18px;font-weight:bold;color:var(--blu)}.cat>summary{font-weight:bold}
.assente{color:#888}.livello{display:inline-block;background:var(--azz);border-radius:4px;padding:0 6px;margin-right:6px;font-size:12px}
.quando{color:#777;font-size:12px}.percorso{word-break:break-all}ul{margin:2px 0 6px;padding-left:20px}
pre{background:var(--grigio);padding:8px;border-radius:4px;overflow-x:auto;font-size:12px}
.avviso{background:var(--aran-ch);border-left:4px solid var(--aran);padding:6px 10px;margin:4px 0}
.conflitto{border-left:4px solid var(--aran);padding-left:8px;margin:6px 0}.fonte{font-size:12px;color:#777}
table{border-collapse:collapse}td,th{border:1px solid var(--grigio);padding:4px 8px;text-align:left}
'''

JS = '''
document.querySelectorAll('.schede button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.schede button,.pannello').forEach(x=>x.classList.remove('attiva','attivo'));
 b.classList.add('attiva');document.getElementById(b.dataset.p).classList.add('attivo');});
'''


def h(t) -> str:
    return html.escape(str(t))


def html_sezioni(nodo) -> str:
    out = ''
    if nodo['voci']:
        out += '<ul>' + ''.join(f'<li>{h(v)}</li>' for v in nodo['voci']) + '</ul>'
    for c in nodo['codice']:
        out += f'<pre>{h(c)}</pre>'
    for f in nodo['figli']:
        out += f'<details open><summary>{h("#" * f["livello"])} {h(f["titolo"])}</summary>{html_sezioni(f)}</details>'
    return out


def html_voce(v: Voce, tutti: bool) -> str:
    if not v.esiste:
        return f'<div class="assente">– <span class="livello">{h(v.livello)}</span><span class="percorso">{h(corto(v.percorso))}</span></div>' if tutti else ''
    tok = v.analisi.get('token')
    info = ' · '.join(x for x in (v.quando, f'~{tok} token' if tok else '', v.nota) if x)
    corpo = ''
    fm = v.analisi.get('frontmatter') or {}
    if fm:
        corpo += '<table>' + ''.join(f'<tr><th>{h(k)}</th><td>{h(val)}</td></tr>' for k, val in fm.items()) + '</table>'
    if 'sezioni' in v.analisi:
        corpo += html_sezioni(v.analisi['sezioni'])
    if v.analisi.get('righe'):
        corpo += '<ul>' + ''.join(f'<li>{h(r)}</li>' for r in v.analisi['righe']) + '</ul>'
    corpo += ''.join(html_voce(f, tutti) for f in v.figli)
    return (f'<details><summary>✓ <span class="livello">{h(v.livello)}</span><span class="percorso">{h(corto(v.percorso))}</span> '
            f'<span class="quando">{h(info)}</span></summary>{corpo}</details>')


def scrivi_html(percorso, progetto, voci, effettive, gruppi, duplicati, sem, avvisi, tutti):
    gerarchia = ''
    for agente in dict.fromkeys(v.agente for v in voci):
        sue = [v for v in voci if v.agente == agente]
        parti = ''
        for cat in CATEGORIE:
            elenco = [v for v in sue if v.categoria == cat]
            if elenco and (tutti or any(v.esiste for v in elenco)):
                parti += (f'<details class="cat" open><summary>{h(cat)} ({sum(v.esiste for v in elenco)})</summary>'
                          + ''.join(html_voce(v, tutti) for v in elenco) + '</details>')
        if agente == 'Claude Code' and effettive:
            parti += ('<details class="cat"><summary>Impostazioni effettive (chi vince)</summary><ul>'
                      + ''.join(f'<li>{h(r)}</li>' for r in effettive) + '</ul></details>')
        gerarchia += f'<details class="agente" open><summary>{h(agente)} – {sum(v.esiste for v in sue)} file</summary>{parti}</details>'

    argomenti = ''
    for arg, elenco in gruppi.items():
        if elenco:
            argomenti += (f'<details class="cat"><summary>{h(arg)} ({len(elenco)})</summary><ul>'
                          + ''.join(f'<li>{h(t)} <span class="fonte">{h(v.lettori)} · {h(corto(v.percorso))}'
                                    f'{" › " + h(s) if s else ""}</span></li>' for v, s, t in elenco) + '</ul></details>')
    if duplicati:
        argomenti += ('<details class="cat" open><summary>Duplicati</summary>'
                      + ''.join(f'<div class="conflitto">“{h(t)}”<br><span class="fonte">'
                                + '<br>'.join(h(x) for x in sorted({str(f.percorso) for f in fonti})) + '</span></div>'
                                for t, fonti in duplicati) + '</details>')

    schede = [('gerarchia', 'Gerarchia', gerarchia), ('argomenti', 'Argomenti', argomenti)]
    if sem:
        corpo = ''
        for a in sem.get('argomenti', []):
            corpo += (f'<details class="cat" open><summary>{h(a.get("nome"))}</summary><p>{h(a.get("sintesi", ""))}</p><ul>'
                      + ''.join(f'<li>{h(r.get("testo"))} <span class="fonte">{h(", ".join(r.get("fonti", [])))}</span></li>'
                                for r in a.get('regole', [])) + '</ul></details>')
        for titolo, chiave in (('Conflitti', 'conflitti'), ('Duplicati', 'duplicati')):
            if sem.get(chiave):
                corpo += (f'<h3>{titolo}</h3>' + ''.join(
                    f'<div class="conflitto">{h(c.get("descrizione"))} <span class="fonte">{h(", ".join(c.get("fonti", [])))}</span></div>'
                    for c in sem[chiave]))
        if sem.get('lacune'):
            corpo += '<h3>Lacune</h3><ul>' + ''.join(f'<li>{h(testo_lacuna(l))}</li>' for l in sem['lacune']) + '</ul>'
        schede.append(('semantica', 'Analisi semantica', corpo))
    schede.append(('avvisi', f'Avvisi ({len(avvisi)})',
                   ''.join(f'<div class="avviso">{h(a)}</div>' for a in avvisi) or '<p>Nessun avviso.</p>'))

    bottoni = ''.join(f'<button data-p="{i}"{" class=attiva" if n == 0 else ""}>{h(t)}</button>' for n, (i, t, _) in enumerate(schede))
    pannelli = ''.join(f'<div class="pannello{" attivo" if n == 0 else ""}" id="{i}">{c}</div>' for n, (i, _, c) in enumerate(schede))
    pagina = (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              f'<title>Agenti di coding</title><style>{CSS}</style></head><body>'
              f'<h1>Che cosa leggono gli agenti</h1><div class="sotto">{h(progetto)} · {h(SISTEMA)}</div>'
              f'<div class="schede">{bottoni}</div>{pannelli}<script>{JS}</script></body></html>')
    Path(percorso).write_text(pagina, encoding='utf-8')


# --------------------------------------------------------------------------- main

def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='Che cosa leggono Claude Code, Codex e Copilot in una cartella di progetto.')
    ap.add_argument('cartella', nargs='?', default='.', help='cartella di progetto (predefinita: quella corrente)')
    ap.add_argument('--agenti', default='claude,codex,copilot', help='quali agenti: claude,codex,copilot')
    ap.add_argument('--html', metavar='FILE', help='scrive anche un report HTML')
    ap.add_argument('--semantico', action='store_true', help='raggruppa e confronta le regole con Claude Code (claude -p)')
    ap.add_argument('--tutti', action='store_true', help='mostra anche i percorsi controllati ma non presenti')
    ap.add_argument('--profondita', type=int, default=6, help='quanto scendere nelle sottocartelle (predefinito 6)')
    ap.add_argument('--dettaglio', action='store_true', help='sul terminale mostra tutte le regole (l’HTML le ha sempre)')
    ap.add_argument('--larghezza', type=int, default=120, help='taglia le righe lunghe (0 = mai)')
    args = ap.parse_args()

    global DETTAGLIO
    DETTAGLIO = args.dettaglio
    progetto = Path(args.cartella).expanduser().resolve()
    if not progetto.is_dir():
        print(f'Cartella non trovata: {progetto}', file=sys.stderr)
        return 1
    scelti = {a.strip().lower() for a in args.agenti.split(',')}
    voci: list[Voce] = []
    if 'claude' in scelti:
        voci += claude_code(progetto, args.profondita)
    if 'codex' in scelti:
        voci += codex(progetto, args.profondita)
    if 'copilot' in scelti:
        voci += copilot(progetto, args.profondita)

    avvisi: list[str] = []
    for v in voci:
        analizza(v, avvisi)
    uniti: dict[str, list[str]] = {}
    for a in avvisi:
        agente, _, resto = a.partition(': ')
        uniti.setdefault(resto or a, []).append(agente)
    avvisi = [f'{" / ".join(dict.fromkeys(ag))}: {testo}' for testo, ag in uniti.items()]
    effettive = impostazioni_effettive(voci)
    gruppi, duplicati = per_argomento(voci)

    sem = None
    if args.semantico:
        print('Analisi semantica con claude -p in corso (può richiedere qualche minuto)…', file=sys.stderr)
        sem, errore = semantico(voci)
        if errore:
            avvisi.append(errore)

    print(f'Progetto: {progetto}   Sistema: {SISTEMA}   Utente: {HOME}')
    stampa(voci, effettive, gruppi, duplicati, sem, avvisi, args)
    if args.html:
        scrivi_html(args.html, progetto, voci, effettive, gruppi, duplicati, sem, avvisi, args.tutti)
        print(f'\nReport HTML: {Path(args.html).resolve()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
