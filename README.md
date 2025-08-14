# FotoMind — Photo Cataloging & Quality Analysis System

## Overview
**FotoMind** è un sistema per catalogare, analizzare e valutare le foto scattate con fotocamere reflex (es. Sony A7 II).  
Il sistema utilizza AI accelerata da Google Coral TPU per:
- Riconoscimento di scena e oggetti
- Riconoscimento volti familiari
- Valutazione qualità foto (nitidezza, esposizione, colore, rumore)
- Generazione automatica di titoli e tagging
- Navigazione e gestione del catalogo tramite interfaccia web

---

## Funzionalità Principali
1. Caricamento foto RAW/JPG.
2. Analisi AI per scena, volti e qualità tecnica.
3. Generazione automatica di titoli e tag.
4. Catalogazione per persona, scena, data e punteggio qualità.
5. Interfaccia web interattiva per:
   - Navigazione e ricerca avanzata
   - Ordinamento per qualità o persona
   - Modifica titoli e aggiunta tag manuali
   - Dashboard statistiche e suggerimenti "Best of"

---

## Tecnologie
- **Backend:** Python (FastAPI o Flask)
- **AI:** TensorFlow Lite / Edge TPU (MobileNetV3, EfficientNet Lite, FaceNet / BlazeFace)
- **Database:** SQLite (MVP) / PostgreSQL (fase avanzata)
- **Frontend:** React o Vue.js
- **Testing:** PyTest / Jest

---

## Setup Ambiente Python

1. Creare e attivare un virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux / Mac
venv\Scripts\activate     # Windows
