# Formazione AI Sistemya – prima giornata

Materiale per la prima giornata del corso di formazione sull'Intelligenza Artificiale per Sistemya.

## Contenuto della repository

- **`Formazione_AI_Sistemya.pptx`** — la presentazione della giornata. Solo testo e diagrammi con forme modificabili; i riquadri tratteggiati "[Immagine]" indicano dove mettere un'immagine.
- **`notebook/`** — i notebook Jupyter usati nei laboratori pratici (vedi elenco sotto).
- **`pomeriggio-dev/`** — materiale per la parte "dev" del pomeriggio (vedi sezione dedicata sotto).

## Notebook

| Notebook | Argomento |
|---|---|
| `00_tensori.ipynb` | Tensori |
| `01_perceptron.ipynb` | Un neurone a mano, le porte logiche, il perceptron che impara |
| `01a_gatto_regole.ipynb` | Classificare un gatto: le regole |
| `01b_gatto_esempi.ipynb` | Classificare un gatto: gli esempi |
| `01b_gravita_neurone.ipynb` | Il neurone applicato alla gravità |
| `01c_gatto_esempi.ipynb` | Classificare un gatto: gli esempi (variante) |
| `01d_gravita_rete.ipynb` | Una rete applicata alla gravità |
| `02_regressione_case.ipynb` | Prezzi delle case: dati sporchi, retta, errore, overfitting |
| `02a_gravita_neurone.ipynb` | Il neurone applicato alla gravità (variante) |
| `02b_gravita_rete.ipynb` | Una rete applicata alla gravità (variante) |
| `03_llm_token.ipynb` | Token, probabilità della parola successiva, temperatura, allucinazioni |
| `04_attention.ipynb` | Q, K, V calcolati a mano; la matrice di attention; il costo del contesto |
| `05_agente.ipynb` | Un piccolo agente con un modello che gira in Colab e due strumenti |
| `teorema_fondamentale_aritmetica.ipynb` | Il teorema fondamentale dell'aritmetica |

## pomeriggio-dev

`pomeriggio-dev/ispeziona_agenti.py` — che cosa leggono **Claude Code**, **Codex** e **GitHub Copilot** quando lavorano in una cartella di progetto: file di istruzioni, impostazioni, skill, agenti, comandi, server MCP, in ordine di caricamento, e che cosa c'è dentro.

Serve solo Python 3.11 o successivo, senza librerie da installare. Funziona su Windows, Linux e macOS.

### Uso

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

### Le due viste

- **Gerarchia**: per ogni agente, i file in ordine di caricamento, con il livello (gestito, utente, progetto, locale, cartella superiore, sottocartella, importato), quando vengono letti (all'avvio, su richiesta, solo per certi file) e il loro contenuto diviso in sezioni e regole. Per Claude Code mostra anche quale impostazione vince quando la stessa chiave è in più file.
- **Argomenti**: le regole di istruzioni e impostazioni raggruppate per tema (build e test, git e PR, stile, database, sicurezza…). Senza `--semantico` la classificazione è per parole chiave, quindi approssimativa; con `--semantico` la fa Claude.

### Limiti da sapere

- I percorsi seguono la documentazione ufficiale di novembre 2026; gli agenti cambiano spesso.
- Il conteggio dei token è una stima (circa 4 caratteri per token).
- Il programma legge soltanto: non modifica nessun file. Con `--semantico` il contenuto delle regole viene inviato a Claude, come in una normale sessione.
- I valori che sembrano segreti (chiavi, token, password) non vengono mostrati.

## Struttura della presentazione

Riferita a `Formazione_AI_Sistemya.pptx`. Solo testo e diagrammi con forme modificabili; i riquadri tratteggiati "[Immagine]" indicano dove mettere un'immagine.

🖼 = segnaposto immagine, con la slide di origine nei deck esistenti.

Etichette (riquadro arancione in alto a destra, da togliere dopo):
- **SOLO DEV**: nascondere per Service e Management.
- **DEV + SERVICE**: nascondere per Management.
- Nessuna etichetta: per tutti.

### Apertura

1. Copertina 🖼 cervello stilizzato con circuiti (AI4B 1)
2. Di che cosa parleremo 🖼 icona cervello e circuiti (AI4B 2)
3. Mattina e pomeriggio

### Che cos'è l'Intelligenza Artificiale

4. Divisore: Che cos'è l'Intelligenza Artificiale
5. Intelligenza Artificiale
6. I campi dell'AI 🖼 segnaposto "You are here" (AI4B 3)
7. Le discipline dietro l'AI
8. Citazione: "L'ignoranza è la più grande delle sofferenze.…" (Dhammapada, v. 243) 🖼 fiori di loto (AI4B 4)
9. AI, Machine Learning, Deep Learning
10. Razionalità limitata 🖼 foto di Herbert Simon (AI4B 6)
11. Anche le regole ci limitano 🖼 foto di Massimo Recalcati (AI4B 7)
12. Come si progetta un sistema AI?
13. Risorse scarse 🖼 schema ambiente → sensori → agente → azione (AI4B 10)
14. Come si progetta un sistema AI? — evidenziato: Euristiche
15. Euristiche
16. Citazione: "Prima costava 3000 €, quindi 1500 € è un affare.…" (Euristica dell'ancoraggio) 🖼 app con prezzi e offerte (AI4B 12)
17. Citazione: "Me lo sento: è la scelta giusta.…" (Euristica dell'affetto – Richard Burton: 8 matrimoni, 2 con la stessa donna) 🖼 Warhol, Liz Taylor (AI4B 13)
18. Citazione: "Ne ho già sentito parlare, quindi è migliore.…" (Euristica della familiarità) 🖼 prodotti di marca famosi (AI4B 14)
19. Anche l'AI usa euristiche
20. Come si progetta un sistema AI? — evidenziato: Satisficing
21. Satisficing 🖼 immagine "va bene così" (The next step 15)
22. Anche l'AI fa satisficing

### 1. Machine Learning

23. Divisore: Machine Learning — Come impara una macchina
24. Programmazione tradizionale
25. Machine Learning
26. Classificare un gatto: le regole
27. Le regole non bastano 🖼 gatto mimetizzato sul divano (Misquoting Truth 31)
28. Classificare un gatto: gli esempi
29. Citazione: "Un sistema impara se migliora le sue prestazioni con l'esper…" (Herbert Simon) 🖼 foto di Herbert Simon (The next step 19)
30. Apprendimento = < T, P, E >
31. T – Compito: classificazione 🖼 lattina di SPAM (The next step 23)
32. T – Compito: regressione 🖼 skyline di Milano (The next step 31)
33. T – Compito: clustering 🖼 logo Amazon (The next step 42)
34. T – Compito: associazione 🖼 birra e patatine (The next step 21)
35. P – Prestazione
36. E – Esperienza: dati etichettati
37. E – Esperienza: dati non etichettati 🖼 apprendimento supervisionato e non (The next step 46)
38. Quando ha senso il Machine Learning?
39. Il vincolo vero
40. Citazione: "Un algoritmo di ML entra in un bar. Il barista chiede: "Cosa…" (Barzelletta)
41. Citazione: "Se tutti i tuoi amici si buttano nel pozzo, ti butti anche t…" (Barzelletta) 🖼 pozzo (The next step 57)
42. Il cervello: una rete 🖼 cervello metà organico metà nuvola (AI4B 17)
43. Il neurone biologico 🖼 neurone stilizzato (AI4B 19)
44. Il cervello è veloce 🖼 grafico velocità del sistema visivo, 150 ms (AI4B 20)
45. Il soma decide 🖼 neurone (AI4B 21)
46. Pesi sinaptici 🖼 schema "synaptic weights" (AI4B 23)
47. La sinapsi 🖼 sinapsi elettrica e chimica (AI4B 24)
48. Imparare = cambiare i pesi 🖼 neurone al microscopio (AI4B 25)
49. Divisione del lavoro 🖼 Khaby Lame e sequenza di immagini (AI4B 26)
50. Il neurone artificiale (McCulloch e Pitts, 1943)
51. Esempio: vado al cinema?
52. Proviamo
53. Porta logica AND **[SOLO DEV]**
54. Porta logica OR **[SOLO DEV]**
55. La soglia decide **[SOLO DEV]**
56. Porta logica XOR **[SOLO DEV]**
57. Perché XOR è impossibile **[SOLO DEV]**
58. La soluzione: più strati **[SOLO DEV]**
59. Il perceptron (Rosenblatt, 1958) **[SOLO DEV]** 🖼 Rosenblatt e il Mark I Perceptron (Misquoting Truth 48)

### 2. Google Colab

60. Divisore: Google Colab — Python nel browser
61. Che cos'è Google Colab 🖼 schermata di Google Colab
62. Un notebook
63. Perché Python 🖼 pitone (Misquoting Truth 6)
64. Le librerie che useremo
65. Zero codice su misura 🖼 mattoncini Lego (Misquoting Truth 7)
66. Come si apre un notebook
67. GPU gratuita
68. Attenzione
69. Laboratorio: 01_perceptron.ipynb — Un neurone a mano, le porte logiche, il perceptron che impara.

### 1. Machine Learning

70. Divisore: Machine Learning — Seconda parte: imparare dai dati
71. Il ciclo di apprendimento
72. Regressione lineare
73. La formula 🖼 ritratto di Sir Francis Galton (Misquoting Truth 59)
74. Funzione di costo
75. Discesa del gradiente **[SOLO DEV]**
76. Il passo giusto **[SOLO DEV]**
77. Dati, verifica, test
78. I dati sono sporchi 🖼 vignetta Dilbert sui numeri inventati (The next step 60)
79. Garbage in, garbage out
80. Dati e informazione
81. Il contesto dà il significato
82. Informazione = dato + contesto
83. Overfitting 🖼 vignetta R² = 0,06 / costellazione "Rexthor" (The next step 67)
84. Overfitting: un esempio
85. Il compromesso 🖼 bersagli bias / varianza (The next step 64)
86. Laboratorio: 02_regressione_case.ipynb — Prezzi delle case: dati sporchi, retta, errore, overfitting.
87. Citazione: "Tutti i modelli sono sbagliati, ma alcuni sono utili.…" (George E. P. Box) 🖼 foto di George Box (Misquoting Truth 66)
88. Un modello è una mappa
89. Citazione: "Nessun algoritmo è il migliore per tutti i problemi.…" (Teorema "No Free Lunch") 🖼 topo e trappola con formaggio (Misquoting Truth 95)

### 3. LLM

90. Divisore: LLM — Large Language Model
91. Che cos'è un LLM
92. Token: i pezzi del testo
93. Prevedere il token successivo
94. Generare = ripetere
95. Parametri
96. Le dimensioni 🖼 cervello metà organico metà digitale "LLM" (AI4B 18)
97. Come impara un LLM 🖼 cervello digitale "APPLE", rete statistica (AI4B 31)
98. Come impara un bambino 🖼 bambino che gioca con una mela (AI4B 30)
99. Bambino e LLM
100. Da modello ad assistente
101. Temperatura
102. Allucinazioni
103. Perché succede
104. Laboratorio: 03_llm_token.ipynb — Token, probabilità della parola successiva, temperatura, allucinazioni.
105. Il "pappagallo stocastico" 🖼 pappagallo nella giungla (AI4B 36)
106. Noam Chomsky 🖼 foto di Noam Chomsky (AI4B 38)
107. Il dibattito 🖼 foto di Geoffrey Hinton (The next step 40)
108. Chi ha ragione?
109. Finestra di contesto
110. Niente memoria tra conversazioni
111. Come usarlo bene

### 4. Transformers

112. Divisore: Transformers — Il motore degli LLM
113. 2017: "Attention Is All You Need"
114. Prima e dopo
115. Embedding
116. Embedding: parole vicine
117. Attention
118. Attention: un esempio
119. Query, Key, Value **[DEV + SERVICE]**
120. Wq, Wk, Wv **[SOLO DEV]**
121. La matrice di attention **[SOLO DEV]**
122. Una tabella n × n **[SOLO DEV]**
123. Il contesto costa
124. Teste multiple
125. Strati
126. Il transformer in una slide
127. Laboratorio: 04_attention.ipynb — Q, K, V calcolati a mano; la matrice di attention; il costo del contesto.
128. Regressione e modelli generativi
129. Comprimere e ricreare **[DEV + SERVICE]**
130. Il modello "sogna" **[DEV + SERVICE]** 🖼 cifre scritte a mano MNIST (The next step 89)

### 5. Agenti AI

131. Divisore: Agenti AI — Dall'assistente che risponde all'assistente che agisce
132. Chatbot e agente
133. Agente = LLM + strumenti + ciclo
134. Il ciclo dell'agente
135. Esempio
136. L'LLM non esegue niente
137. Laboratorio: 05_agente.ipynb — Un piccolo agente con un modello che gira in Colab e due strumenti.
138. Claude Code
139. Il contesto del progetto: CLAUDE.md
140. La cartella .claude
141. Permessi
142. I limiti
143. Cosa non delegare
144. La responsabilità resta nostra
145. Citazione: "Tutti i modelli sono sbagliati, ma alcuni sono utili.…" (George E. P. Box) 🖼 foto di George Box (Misquoting Truth 66)
146. Domande
147. Dopo pranzo
