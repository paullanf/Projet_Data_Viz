# 📊 Projet_Data_Viz

## 👥 Membres du groupe

* **Jeromsan JUDES RAMESH**
* **Omar ABDELRAHMAN**
* **Paul LANFRANCHI**
* **Ines YAICI**
* **Eglantine DILLIES**
* **Anne Laure MUGISHA GAKWANDI**
  
– Cohortes, RFM & CLV (Online Retail II)

Application d’aide à la décision marketing basée sur :

* l’analyse de **cohortes d’acquisition**
* la **segmentation RFM** (Recency–Frequency–Monetary)
* l’estimation de la **Customer Lifetime Value (CLV)**
* la **simulation de scénarios business** (rétention, remise, marge)

L’application est développée en **Streamlit** et s’appuie sur le dataset **Online Retail II** (UCI), contenant les transactions e-commerce d’un détaillant UK entre le 01/12/2009 et le 09/12/2011 (~1,07M lignes).

---

## 🧩 Objectifs business

* **Mesurer la rétention** par cohortes (M+1, M+2, …) et la dynamique de revenu.
* **Construire des segments RFM** pour prioriser les actions marketing.
* **Estimer la CLV** via :

  * une approche empirique (CA moyen par client),
  * une formule fermée basée sur la marge (m), la rétention (r) et le taux d’actualisation (d).
* **Tester des scénarios** (+5 % de rétention, −10 % de marge, remise…) et mesurer l’impact sur :

  * la CLV,
  * le CA,
  * la rétention.

---

## 📂 Jeu de données

* **Source** : Online Retail II – UCI Machine Learning Repository
* **Période couverte** : 01/12/2009 → 09/12/2011
* **Volume** : ~1,07 million de lignes
* **Colonnes clés** :

  * `InvoiceNo`, `InvoiceDate`
  * `CustomerID`, `Country`
  * `Quantity`, `UnitPrice`
  * `Amount` *(créée dans le code = Quantity × UnitPrice)*

Les fichiers ne sont **pas versionnés** dans le repo : ils sont **chargés à la volée via l’interface Streamlit** (upload `.csv` ou `.xlsx`).

---

## 🚀 Installation

### 🔧 1. Cloner le repository

```bash
git clone https://github.com/paullanf/Projet_Data_Viz.git
cd Projet_Data_Viz
```

### 📦 2. Créer et activer un environnement virtuel (recommandé)

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
```

### 🧩 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## 🧪 Lancer le notebook d'exploration (avant l'app)

Le dossier `notebooks/` contient un notebook d'analyse préliminaire permettant :

* d'explorer les données brutes,
* de visualiser les distributions,
* de vérifier la qualité des données,
* d'obtenir un aperçu des cohortes, RFM et comportements clients.

### ▶️ Exécuter le notebook

Assurez-vous d'être dans l'environnement virtuel puis lancez :

```bash
jupyter notebook notebooks/01_exploration.ipynb
```

Ou démarrez simplement Jupyter puis ouvrez le fichier depuis l'interface.

Ce notebook n'est **pas obligatoire** pour faire tourner l'application, mais il permet de comprendre et valider le pipeline analytique avant l'utilisation de Streamlit.

---

## ▶️ Utilisation de l’application

### 1. Lancer l’application Streamlit

```bash
streamlit run app/app.py
```

### 2. Charger les données

Dans l’interface Streamlit :

1. Importer un fichier **Online Retail II** (`.csv` ou `.xlsx`).
2. L’application détecte automatiquement les colonnes nécessaires.
3. Les analyses deviennent disponibles : Cohortes, RFM, CLV, Simulations.

### 3. Fonctionnalités accessibles dans le menu latéral

* **📆 Cohortes d’acquisition**

  * suivi M+1, M+2...
  * taux de rétention et revenu par cohorte
* **🧮 Segmentation RFM**

  * scoring R-F-M
  * heatmaps et clusterisation
* **💰 Estimation CLV**

  * méthodes empirique et analytique
* **🧪 Simulation business**

  * impact d’une variation de la rétention
  * impact d’une remise ou baisse de marge
  * projection CA / marge / CLV

---

## 🏗️ Architecture du projet

```
Projet_Data_Viz/
├── app/
│   ├── app.py               # Application principale Streamlit
│   └── utils.py             # Fonctions métier & traitements
├── notebooks/
│   └── 01_exploration.ipynb # Notebook d’exploration visuelle
├── data/
│   ├── raw/                 # Fichiers bruts (Online Retail II)
│   └── processed/           # Données transformées
├── docs/
│   └── prez/                # Slides de présentation
├── requirements.txt
└── README.md
```

---

## 📎 Lien du repository

GitHub : [https://github.com/paullanf/Projet_Data_Viz](https://github.com/paullanf/Projet_Data_Viz)
