# ispeziona_agenti.py

Che cosa leggono **Claude Code**, **Codex** e **GitHub Copilot** quando lavorano in una cartella di progetto:
file di istruzioni, impostazioni, skill, agenti, comandi, server MCP, in ordine di caricamento,
e che cosa c'è dentro.

Serve solo Python 3.11 o successivo, senza librerie da installare. Funziona su Windows, Linux e macOS.

## Uso

```
python ispeziona_agenti.py C:\repos\Armonya-Next
python ispeziona_agenti.py . --html report.html
python ispeziona_agenti.py . --semantico --html report.html
```

| Opzione | Effetto |
|---|---|
| `--html FILE` | report da aprire nel browser: schede Gerarchia, Argomenti, Avvisi (e Analisi semantica) |
| `--semantico` | fa leggere le regole a Claude Code (`claude -p`), che le raggruppa per tema e trova duplicati, conflitti e lacune. Serve Claude Code installato e collegato al proprio account |
| `--agenti claude,codex,copilot` | limita l'analisi ad alcuni agenti |
| `--tutti` | mostra anche i percorsi controllati dove non c'è nessun file (utile per sapere dove si possono mettere) |
| `--dettaglio` | sul terminale mostra tutte le regole; senza, solo i titoli delle sezioni con il numero di regole |
| `--profondita N` | quanto scendere nelle sottocartelle per cercare CLAUDE.md e AGENTS.md (predefinito 6) |

## Le due viste

- **Gerarchia**: per ogni agente, i file in ordine di caricamento, con il livello (gestito, utente, progetto,
  locale, cartella superiore, sottocartella, importato), quando vengono letti (all'avvio, su richiesta,
  solo per certi file) e il loro contenuto diviso in sezioni e regole.
  Per Claude Code mostra anche quale impostazione vince quando la stessa chiave è in più file.
- **Argomenti**: le regole di istruzioni e impostazioni raggruppate per tema (build e test, git e PR, stile,
  database, sicurezza…). Senza `--semantico` la classificazione è per parole chiave, quindi approssimativa;
  con `--semantico` la fa Claude.

## Limiti da sapere

- I percorsi seguono la documentazione ufficiale di novembre 2026; gli agenti cambiano spesso.
- Il conteggio dei token è una stima (circa 4 caratteri per token).
- Il programma legge soltanto: non modifica nessun file. Con `--semantico` il contenuto delle regole
  viene inviato a Claude, come in una normale sessione.
- I valori che sembrano segreti (chiavi, token, password) non vengono mostrati.
