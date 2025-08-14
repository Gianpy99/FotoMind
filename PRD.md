# FotoMind — Photo Cataloging & Quality Analysis System

## **1. Overview**
**FotoMind** è un sistema per catalogare, analizzare e valutare le foto scattate con fotocamere reflex (es. Sony A7 II).  
Obiettivi principali:
- Generazione automatica di titoli basati su scena, oggetti e volti riconosciuti.
- Valutazione della qualità della foto (nitidezza, colore, esposizione, rumore).
- Riconoscimento di volti familiari per organizzazione personalizzata.
- Navigazione e gestione del catalogo tramite interfaccia web.

---

## **2. Scopo**
Fornire uno strumento che permetta di:
- Catalogare automaticamente foto personali.
- Valutare la qualità tecnica delle foto.
- Riconoscere persone chiave e scene ricorrenti.
- Fornire un’interfaccia web interattiva per esplorare e filtrare il catalogo.

---

## **3. Requisiti Funzionali**
1. Caricamento foto RAW/JPG.
2. Analisi AI per:
   - Riconoscimento scena/oggetti.
   - Riconoscimento volti.
   - Valutazione qualità foto (nitidezza, esposizione, colore, rumore).
3. Generazione automatica di titoli e tagging.
4. Catalogazione per persona, scena, data, punteggio qualità.
5. Interfaccia web per:
   - Navigazione e ricerca avanzata.
   - Ordinamento per punteggio qualità o persona.
   - Zoom e preview thumbnail.
   - Modifica titoli e aggiunta tag manuali.
6. Suggerimenti automatici “Best of” (fase avanzata).

---

## **4. Requisiti Non Funzionali**
- Supporto per Edge TPU (Google Coral) per accelerare l’inferenza AI.
- Database leggero (SQLite) per MVP, scalabile a PostgreSQL.
- API RESTful per comunicazione tra backend AI e frontend.
- Web UI responsive e mobile-friendly.
- Sicurezza e gestione accessi per eventuale uso remoto.

---

## **5. Tecnologie e Modelli AI**
- **Riconoscimento oggetti/scena:** MobileNetV3, EfficientNet Lite (Edge TPU)
- **Riconoscimento volti:** FaceNet / BlazeFace (Edge TPU)
- **Valutazione qualità foto:** algoritmi nitidezza (Laplacian/FFT), analisi esposizione e colore
- **Database:** SQLite (MVP) / PostgreSQL (fase avanzata)
- **Web UI:** React o Vue.js
- **Backend:** Python (FastAPI o Flask)

---

## **6. Pianificazione per Fasi**

### **Fase 1 — MVP**
- Caricamento foto e analisi base oggetti/volti.
- Titoli automatici semplici.
- Catalogo ricercabile per persona/scena.
- Web UI: griglia immagini + filtri base.

### **Fase 2**
- Valutazione qualità foto avanzata.
- Miglioramento titoli con contesto più dettagliato.
- Tagging avanzato per oggetti secondari.
- Web UI avanzata: zoom full-screen, modifica titoli, ordinamento per qualità, tagging interattivo.

### **Fase 3**
- Suggerimenti “best of week”.
- Aggiornamento volti/familiari (apprendimento incrementale).
- Dashboard statistiche e grafici sul catalogo.
- Accesso remoto sicuro e interfaccia mobile-friendly.

---

## **7. Blueprint Tecnico**

| Fase | Input | Modello / Tecnologia | Elaborazione / Funzione | Output | TPU Compatibilità | Web UI |
|------|-------|--------------------|-----------------------|--------|-----------------|--------|
| MVP | Foto RAW/JPG | EdgeTPU MobileNetV3 / EfficientNet Lite, FaceNet / BlazeFace | Riconoscimento scena/oggetti e volti, generazione titoli base | Titolo, persone rilevate, metadati EXIF | Sì | Griglia immagini, filtri base |
| Fase 2 | Foto analizzate MVP | EdgeTPU qualità foto (nitidezza, colore, esposizione) | Valutazione qualità, miglioramento titoli, tagging avanzato | Punteggio qualità, titoli migliorati, tag dettagliato | Sì | Zoom full-screen, ordinamento per qualità, modifica titoli, tagging interattivo |
| Fase 3 | Catalogo completo + storico | Apprendimento incrementale volti, event detection AI | Suggerimenti “best of”, aggiornamento volti/familiari, statistiche | Suggerimenti foto principali, database volti aggiornato, grafici | Opzionale | Dashboard statistiche, mobile-friendly UI, filtri avanzati |

---

## **8. Note Implementative**
- TPU Edge permette inferenza veloce anche su dataset medio-piccoli.
- Titoli e punteggi qualità possono essere aggiornati incrementando il dataset.
- Web UI può essere inizialmente locale, estendibile a accesso cloud futuro.
- Possibilità di aggiungere funzionalità di backup e sincronizzazione cloud in fase avanzata.

---

## **9. Roadmap**
1. MVP con caricamento foto, riconoscimento scena/volti e Web UI base.
2. Analisi qualità foto, titoli avanzati, tagging interattivo.
3. Suggerimenti automatici, dashboard statistiche, apprendimento volti incrementale.
