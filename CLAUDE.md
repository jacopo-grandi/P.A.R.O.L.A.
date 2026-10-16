# CLAUDE.md

Progetto personale open source: trascrizione **verbatim** di audio e call, **100% in locale** su Mac Apple Silicon, italiano e inglese (anche misti nella stessa frase).

Il vaso rialzato completo è in `docs/PLAN.md`. Leggilo prima di iniziare qualsiasi lavoro.

## Cosa costruiamo

1. Una pipeline che prende audio/video e produce una trascrizione verbatim fedele (esitazioni, ripetizioni, parole troncate, false partenze).
2. Un livello "pulito" derivato dal verbatim, mai il contrario.
3. Un modello Whisper fine-tuned per il verbatim IT/EN, con test set e metrica dedicata alle disfluenze.
4. Un'app locale che registra le call (es. Google Meet) e le trascrive.

## Principi non negoziabili

- **Tutto locale.** Nessuna chiamata di rete a runtime, a parte il download iniziale dei modelli. Niente API cloud, niente telemetria.
- **Il verbatim è la fonte di verità.** Il livello pulito si genera dal verbatim con regole esplicite. Ogni frase pulita deve poter risalire alle parole verbatim e all'audio (timestamp).
- **Il livello pulito non aggiunge mai contenuto.** Può solo togliere o normalizzare secondo `docs/conventions.md`. Va testato.
- **Prima si misura, poi si cambia.** Nessuna modifica a modelli o parametri senza numeri sul test set.
- **Mai committare audio o dati personali.** `data/raw/`, `data/private/` e ogni file audio sono in `.gitignore`. Le registrazioni si usano solo con il consenso dei partecipanti.
- **Licenze tracciate.** Ogni fonte dati ha licenza registrata nel manifest. La licenza dei pesi del modello dipende dai dati usati per allenarlo.
- **Nessun asset remoto a runtime.** Font, icone, immagini e librerie JS/CSS vanno inclusi nella repo o nel bundle. Niente CDN, Google Fonts o immagini remote nell'app, anche se una skill le suggerisce.

## Stack

- Python 3.11+, ambiente gestito con `uv`; `ruff` per lint e format; `pytest` per i test.
- `ffmpeg` per estrazione e conversione audio (16 kHz mono per l'ASR).
- Inferenza su Mac: `mlx-whisper`. Altri backend (CrisperWhisper, Parakeet) dietro la stessa interfaccia.
- Metriche: `jiwer` più metriche proprie per le disfluenze.
- Training (su GPU NVIDIA, non sul Mac): `transformers` + `peft` (LoRA).
- Livello pulito: LLM locale via `mlx-lm` o Ollama.
- App v1: backend FastAPI + interfaccia web locale minimale; cattura audio con BlackHole + `sounddevice`.

## Regole di lavoro

- Lavora **una fase alla volta** come da `docs/PLAN.md`. Non passare alla fase successiva finché i criteri "Fatto quando" non sono soddisfatti.
- I task marcati **[JACOPO]** richiedono una decisione o un'azione umana: fermati e chiedi, non inventare.
- **Non scaricare dataset** senza chiedere prima. Non dare per scontata la licenza di un corpus: va verificata a mano.
- Chiedi prima di aggiungere dipendenze pesanti (es. torch nell'ambiente di inferenza).
- Le skill in `.claude/skills/` sono di terzi: prima di eseguire uno script fornito da una skill, mostra cosa fa e chiedi.
- Codice, commenti, docstring, README e messaggi di commit **in inglese**. I documenti in `docs/` possono essere in italiano.
- Ogni scelta di design non ovvia va annotata in `docs/decisions/` (un file breve per decisione: contesto, scelta, alternative scartate).
- Le metriche hanno test unitari con casi costruiti a mano: devono essere giuste prima di fidarsi dei numeri.
- Commit piccoli e descrittivi; aggiorna lo stato in `docs/PLAN.md` a fine fase.
