import pandas as pd
import numpy as np
import streamlit as st
import io
import plotly.io as pio

# ---------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------
@st.cache_data
def load_data(uploaded_files):
    """
    Charge le fichier Online Retail II et prépare les colonnes de base.
    [NOUVEAU] Modifié pour accepter une LISTE de fichiers et les fusionner (2009-2011).
    """
    all_dfs = []
    
    # Si aucun fichier n'est fourni, on retourne vide
    if not uploaded_files:
        return pd.DataFrame()

    # Boucle sur chaque fichier uploadé pour les lire
    for file in uploaded_files:
        try:
            if file.name.endswith(".csv"):
                df_temp = pd.read_csv(file, encoding='ISO-8859-1', low_memory=False)
            else:
                df_temp = pd.read_excel(file)
            all_dfs.append(df_temp)
        except Exception as e:
            st.error(f"Erreur lors du chargement de {file.name}: {e}")

    if not all_dfs:
        return pd.DataFrame()

    # Fusion des fichiers
    df = pd.concat(all_dfs, ignore_index=True)

    # Nettoyage noms de colonnes
    df.columns = df.columns.str.strip()

    # Harmonisation des noms
    rename_map = {
        "Invoice": "InvoiceNo",
        "InvoiceNo ": "InvoiceNo",
        "Price": "UnitPrice",
        "Customer ID": "CustomerID",
        "CustomerID ": "CustomerID"
    }
    df = df.rename(columns=rename_map)


    df = df.dropna(subset=["CustomerID"]).copy()
    
    # Conversion en int puis str pour éviter le format "12345.0"
    df["CustomerID"] = df["CustomerID"].astype(int).astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Amount"] = df["Quantity"] * df["UnitPrice"]

    # Flags utiles
    df["InvoiceMonth"] = df["InvoiceDate"].dt.to_period("M").dt.to_timestamp()
    
    # Ajout .upper() pour robustesse sur le 'C'
    df["is_cancel"] = df["InvoiceNo"].astype(str).str.upper().str.startswith("C")

    return df


# ---------------------------------------------------------
# Fonctions métier
# ---------------------------------------------------------

def apply_filters(df, country_filter, date_range, returns_mode, order_threshold, customer_type):
    """
    Applique les filtres globaux.
    [NOUVEAU] Ajout du filtre 'customer_type' pour répondre au cahier des charges.
    """
    df_f = df.copy()

    # Filtre pays
    if country_filter != "Tous":
        df_f = df_f[df_f["Country"] == country_filter]

    # Filtre dates
    if len(date_range) == 2:
        start, end = date_range
        df_f = df_f[(df_f["InvoiceDate"] >= pd.Timestamp(start)) &
                    (df_f["InvoiceDate"] <= pd.Timestamp(end))]
    
    # Filtre Type Client (Simulation car pas de colonne 'Type' dans le CSV brut)
    # B2B est simulé ici par les ID < 13000 (hypothèse courante sur ce dataset ou arbitraire
    
    if customer_type == "B2B (VIP)":
        df_f = df_f[df_f["CustomerID"].astype(int) < 13000]
    elif customer_type == "B2C (Standard)":
        df_f = df_f[df_f["CustomerID"].astype(int) >= 13000]

    # Filtre retours
    if returns_mode == "Exclure":
        df_f = df_f[(df_f["Quantity"] > 0) & (~df_f["is_cancel"])]
    elif returns_mode == "Neutraliser":
        # On garde les lignes mais on tronque la valeur à 0 minimum
        df_f["Amount"] = df_f["Amount"].clip(lower=0)

    # Seuil de commande (on peut filtrer sur le montant > seuil)
    if order_threshold > 0:
        df_f = df_f[df_f["Amount"] >= order_threshold]

    return df_f


def compute_kpis(df):
    """
     Calcule les KPI globaux en une seule passe pour la page Overview.
    Intègre la logique 'North Star' demandée.
    """
    if df.empty:
        return 0, 0, 0, 0, 0
        
    ca_total = df["Amount"].sum()
    n_clients = df["CustomerID"].nunique()
    panier_moyen = df.groupby("InvoiceNo")["Amount"].sum().mean() # Panier moyen (ligne)
    
    # North Star Metric : % de clients ayant fait > 1 commande sur la période
    freq = df.groupby("CustomerID")["InvoiceNo"].nunique()
    repeat_buyers = freq[freq > 1].count()
    north_star = (repeat_buyers / n_clients * 100) if n_clients > 0 else 0
    
    clv_emp = df.groupby("CustomerID")["Amount"].sum().mean()
    
    return ca_total, n_clients, panier_moyen, north_star, clv_emp


def compute_rfm(df):
    """
    Calcule Recency, Frequency, Monetary par client.
    Calcule aussi 'AvgBasket' (Panier moyen par client) pour le tableau Segments.
    """
    if df.empty:
        return pd.DataFrame()

    NOW = df["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = df.groupby("CustomerID").agg({
        "InvoiceDate": lambda x: (NOW - x.max()).days,
        "InvoiceNo": "nunique",
        "Amount": ["sum", "mean"] # On récupère Somme ET Moyenne
    })
    
    # Aplatir les colonnes MultiIndex
    rfm.columns = ["Recency", "Frequency", "Monetary", "AvgBasket"]
    rfm = rfm.reset_index()

    return rfm


def score_rfm(rfm):
    """
    Ajoute des scores R, F, M (1-5) + segment, en évitant les crashs quand dataset trop petit.
    """
    if rfm.empty or len(rfm) < 5:
        # On retourne un RFM "minimal" et on laisse l’UI afficher un message.
        rfm_copy = rfm.copy()
        rfm_copy["R_score"] = None
        rfm_copy["F_score"] = None
        rfm_copy["M_score"] = None
        rfm_copy["Segment"] = "Données insuffisantes"
        rfm_copy["Action"] = "N/A"
        return rfm_copy

    rfm_scored = rfm.copy()

    try:
        # Recency
        rfm_scored["R_score"] = pd.qcut(
            rfm_scored["Recency"], 5,
            labels=[5, 4, 3, 2, 1],
            duplicates="drop"
        )

        # Frequency
        rfm_scored["F_score"] = pd.qcut(
            rfm_scored["Frequency"].rank(method="first"),
            5,
            labels=[1, 2, 3, 4, 5],
            duplicates="drop"
        )

        # Monetary
        rfm_scored["M_score"] = pd.qcut(
            rfm_scored["Monetary"].rank(method="first"),
            5,
            labels=[1, 2, 3, 4, 5],
            duplicates="drop"
        )

    except ValueError:
        # Si qcut plante, on renvoie une version "minimaliste"
        rfm_scored["R_score"] = None
        rfm_scored["F_score"] = None
        rfm_scored["M_score"] = None
        rfm_scored["Segment"] = "Données insuffisantes"
        rfm_scored["Action"] = "N/A"
        return rfm_scored

    # Mapping de segments
    def label_segment(row):
        r, f, m = int(row["R_score"]), int(row["F_score"]), int(row["M_score"])
        if r >= 4 and f >= 4 and m >= 4:
            return "Champions"
        elif r >= 4 and f >= 3:
            return "Fidèles"
        elif r >= 3 and m >= 3:
            return "Potentiel"
        elif r <= 2 and f >= 3:
            return "À risque"
        else:
            return "Autres"

    rfm_scored["Segment"] = rfm_scored.apply(label_segment, axis=1)
    
    # Ajout d'une colonne 'Action' pour l'export "Liste Activable"
    action_map = {
        "Champions": "Choyer / Upsell VIP",
        "Fidèles": "Programme fidélité",
        "Potentiel": "Offre de bienvenue",
        "À risque": "Réactivation urgente",
        "Autres": "Automation email"
    }
    rfm_scored["Action"] = rfm_scored["Segment"].map(action_map)
    
    return rfm_scored


def compute_cohorts(df):
    """
    Construit une matrice de rétention par cohortes.
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Cohorte = mois de 1er achat
    first_purchase = df.groupby("CustomerID")["InvoiceMonth"].min().reset_index()
    first_purchase.columns = ["CustomerID", "CohortMonth"]
    
    df_cohort = df.merge(first_purchase, on="CustomerID")

    # Age de cohorte en mois
    year_diff = df_cohort["InvoiceMonth"].dt.year - df_cohort["CohortMonth"].dt.year
    month_diff = df_cohort["InvoiceMonth"].dt.month - df_cohort["CohortMonth"].dt.month
    df_cohort["CohortIndex"] = year_diff * 12 + month_diff

    # Rétention : nombre de clients uniques par cohorte/age
    cohort_data = df_cohort.groupby(["CohortMonth", "CohortIndex"])["CustomerID"].nunique().reset_index()
    cohort_pivot = cohort_data.pivot_table(
        index="CohortMonth",
        columns="CohortIndex",
        values="CustomerID"
    )

    # Taille de cohorte = colonne 0
    cohort_sizes = cohort_pivot.iloc[:, 0]
    retention = cohort_pivot.divide(cohort_sizes, axis=0)

    # CA par âge de cohorte (Pour les courbes)
    # On prend la moyenne ici pour normaliser les courbes
    rev_data = df_cohort.groupby(["CohortMonth", "CohortIndex"])["Amount"].mean().reset_index()
    rev_pivot = rev_data.pivot_table(
        index="CohortMonth",
        columns="CohortIndex",
        values="Amount"
    )

    return retention, rev_pivot


def clv_formula(m, r, d):
    """Formule fermée CLV = m * r / (1 + d - r)."""
    denom = 1 + d - r
    if denom <= 0:
        return 0
    return m * r / denom

def simulate_sensitivity(m, current_r, d, steps=20):
    """
    [NOUVEAU] Génère les données pour la courbe de sensibilité (Scénarios).
    Fait varier 'r' (rétention) de 0.1 à 0.99 pour voir l'impact sur la CLV.
    """
    r_values = np.linspace(0.1, 0.99, steps)
    clv_values = [clv_formula(m, r_val, d) for r_val in r_values]
    return r_values, clv_values


def get_cohort_data_for_density(df):
    """
    Prépare les données granulaires pour les courbes de densité (Boxplots).
    Retourne un DataFrame avec : CohortMonth, CohortIndex, et Montant par client.
    """
    if df.empty:
        return pd.DataFrame()

    # Calcul du mois de 1er achat
    first_purchase = df.groupby("CustomerID")["InvoiceMonth"].min().reset_index()
    first_purchase.columns = ["CustomerID", "CohortMonth"]
    
    df_cohort = df.merge(first_purchase, on="CustomerID")

    # Calcul de l'index (Mois 0, 1, 2...)
    year_diff = df_cohort["InvoiceMonth"].dt.year - df_cohort["CohortMonth"].dt.year
    month_diff = df_cohort["InvoiceMonth"].dt.month - df_cohort["CohortMonth"].dt.month
    df_cohort["CohortIndex"] = year_diff * 12 + month_diff
    
    # On agrège le CA par Client et par Index (pour voir la distribution des dépenses)
    # C'est ça qui permet de voir la "densité" 
    df_density = df_cohort.groupby(["CohortMonth", "CohortIndex", "CustomerID"])["Amount"].sum().reset_index()
    
    return df_density

def export_plot_png(fig, filename, filters_text=""):
    """
    Exporte un graphique Plotly en PNG (bytes) avec les filtres affichés dans le titre.
    """
    # On ajoute les filtres sous forme de titre secondaire
    if filters_text:
        fig.update_layout(
            title=dict(
                text=f"{fig.layout.title.text}<br><sup>{filters_text}</sup>"
            )
        )
    buffer = io.BytesIO()
    pio.write_image(fig, buffer, format="png", engine="kaleido")
    buffer.seek(0)
    return buffer.getvalue()
