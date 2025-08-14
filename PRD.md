# PhotoFamily Catalog — PRD

## Titolo del progetto
**PhotoFamily Catalog**  
Catalogazione intelligente di foto reflex con riconoscimento volti familiari, valutazione qualità immagine e titolazione automatica.

---

## Descrizione progetto
Questo progetto permette di organizzare e catalogare le foto scattate con la Sony A7 II. Utilizza moduli AI per:
- Riconoscere persone della famiglia e associare titoli personalizzati
- Valutare qualità delle foto (nitidezza, esposizione, colori)
- Classificare scene e generare titoli automatici
- Fornire un’interfaccia web per navigazione e gestione del catalogo

Il progetto è progettato per essere eseguito su **Google Coral TPU** per inferenze veloci e localmente per preservare la privacy.

---

## Obiettivi principali
1. Automatizzare la catalogazione delle foto
2. Riconoscere volti familiari
3. Valutare qualità delle immagini
4. Generare titoli e descrizioni automatiche
5. Fornire interfaccia web semplice e veloce per navigare il catalogo

---

## Moduli AI

### 1. Modulo Classificazione Scene
- **Obiettivo:** Assegnare categorie generali alla foto (es. “ritratto”, “paesaggio”, “macro”)  
- **Modello consigliato:** EfficientNet-Lite o MobileNetV3 quantizzati per Edge TPU  
- **Input:** immagine RAW o JPEG  
- **Output:** categoria scena + probabilità di confidenza

### 2. Modulo Riconoscimento Volti Familiari
- **Obiettivo:** Identificare persone della famiglia  
- **Modello consigliato:** FaceNet o ArcFace convertiti in TFLite per Edge TPU  
- **Input:** immagine  
- **Output:** embedding del volto → confronto con database locale → nome riconosciuto

### 3. Modulo Valutazione Qualità Foto
- **Obiettivo:** Analizzare nitidezza, esposizione, contrasto e saturazione  
- **Modello consigliato:** NIMA (Neural Image Assessment) ottimizzato per TPU  
- **Input:** immagine  
- **Output:** punteggio qualità + tag automatici (es. “foto nitida”, “colore vivace”)

### 4. Modulo Captioning / Titolo Automatico
- **Obiettivo:** Generare un titolo sintetico o una descrizione breve della foto  
- **Modello consigliato:** Show-and-Tell leggero o BLIP quantizzato per TPU  
- **Input:** immagine classificata + volti riconosciuti  
- **Output:** frase sintetica descrittiva (es. “Marco e Giulia al parco”)  
- **Note:** opzionale nella prima versione

---

## Modulo Interfaccia Web
- **Obiettivo:** Navigare, filtrare e visualizzare le foto catalogate  
- **Tecnologia suggerita:** FastAPI o Flask per backend + React per frontend  
- **Funzionalità principali:**
  - Ricerca per categoria, persona, punteggio qualità
  - Anteprima foto e dettagli
  - Modifica titolo/tag manualmente
  - Dashboard statistiche qualità e riconoscimento

---

## Flusso operativo
1. Foto importata nel sistema
2. Modulo classificazione scena → assegna categoria
3. Modulo riconoscimento volti → identifica membri famiglia
4. Modulo valutazione qualità → assegna punteggio e tag
5. Modulo captioning → genera titolo automatico
6. Salvataggio metadati e foto nel catalogo
7. Accesso via interfaccia web

---

## Planning tecnico e priorità

| Modulo | Priorità | Note | Hardware/Software |
|--------|----------|------|-----------------|
| Classificazione Scene | Alta | Primo step per titolazione | Edge TPU |
| Riconoscimento Volti | Alta | Necessario per titoli familiari | Edge TPU |
| Valutazione Qualità | Media | Utile per filtrare foto migliori | Edge TPU |
| Captioning / Titolo | Bassa | Step opzionale | TPU consigliata, CPU fallback |
| Interfaccia Web | Media | Navigazione e gestione | FastAPI/Flask + React |

---

## Suggerimenti hardware/software
- **Fotocamera:** Sony A7 II  
- **TPU:** Google Coral USB o PCIe  
- **Ambiente Python:** 3.11+, TensorFlow Lite  
- **Database volti/foto:** SQLite o PostgreSQL locale  
- **Sistema operativo consigliato:** Linux o Windows 10/11

---

## README sintetico per GitHub

### PhotoFamily Catalog
Catalogo intelligente di foto reflex con AI per titolazione e riconoscimento volti familiari.

**Funzionalità principali:**
- Classificazione automatica scene
- Riconoscimento volti familiari
- Valutazione qualità foto
- Generazione titolo automatico
- Interfaccia web per gestione e navigazione

**Prerequisiti:**
- Python 3.11+
- Google Coral TPU
- TensorFlow Lite
- FastAPI / Flask + React (opzionale per interfaccia web)

**Installazione:**
```bash
git clone <repo-url>
cd PhotoFamilyCatalog
pip install -r requirements.txt
