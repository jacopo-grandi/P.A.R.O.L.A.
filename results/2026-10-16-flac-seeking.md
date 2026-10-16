# Salti nell'audio: FLAC in WebKit — 2026-10-16

**Perché.** Su en-001 (un'ora) nell'app nativa testo e audio non coincidevano, anche cliccando una parola. I tempi della trascrizione non c'entrano: riascoltando con Whisper 12 punti sparsi, tagliati con ffmpeg dal FLAC e dall'originale m4a, i due tagli danno lo stesso testo in tutti i 12 punti (somiglianza col testo trascritto 0,45–1,00, identica tra FLAC e m4a). Il problema è dove il lettore salta.

**Come.** Un file di prova di un'ora (16 kHz mono, codificato come `parola compress`): rumore forte dal secondo 5 al 30 di ogni minuto, rumore debole dal 40 al 50, silenzio altrove, e un bip a 1 kHz di 0,3 s esattamente su ogni minuto. Una pagina salta a qualche secondo prima di un bip, fa partire l'audio e ascolta con Web Audio quando arriva il bip. Provata in Chromium (il pannello browser) e in una WKWebView come quella dell'app.

**Risultati.**

| Motore | File | Salti | Esito |
|---|---|---|---|
| Chromium | FLAC | 5, da 5 a 59 min | bip esatto: errore 0,01–0,02 s |
| WebKit | WAV | 6, poi 8 ripetuti | bip dove atteso (2,9–3,6 s dopo un salto di 3 s); alcune letture a 0,5 s sono il bip precedente rimasto nel buffer del test |
| WebKit | FLAC | 5 + 6 + 8 | bip quasi mai sentito entro 8 s; una volta 23 s più avanti, una volta quasi giusto (−0,9 s) |
| WebKit | FLAC con SEEKTABLE (360 punti, uno ogni 10 s, campioni identici) | 6 | come senza: bip mai sentito |

**Scelta.** Decisione [0032](../docs/decisions/0032-play-wav-copies-of-flac-calls.md): le call restano FLAC sul disco, al lettore va una copia WAV decodificata all'apertura. Su en-001: 0,6 s la prima volta, poi subito.

**Limiti.** La prova in WebKit misura con Web Audio dentro la pagina, che aggiunge un ritardo variabile all'avvio; per questo il WAV è "dove atteso" e non "esatto al centesimo". La catena intera (server → WAV → WebKit) non è stata misurata col bip; i suoi pezzi sì.
