import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import utils  # [NOTE] On importe le fichier utils.py qu'on vient de créer

# ---------------------------------------------------------
# Config générale
# ---------------------------------------------------------
st.set_page_config(
    page_title="Cohortes & CLV – ECE",
    layout="wide"
)

st.title("Application Marketing – Cohortes, RFM & CLV")

# ---------------------------------------------------------
# Sidebar : upload + filtres + navigation
# ---------------------------------------------------------

st.sidebar.header("Filtres et navigation")

 
# Upload des fichiers (acceptant plusieurs fichiers)
uploaded_files = st.sidebar.file_uploader(
    "Importer le dataset Online Retail II", 
    type=["csv", "xlsx"],
    accept_multiple_files=True 
)

if not uploaded_files:
    st.warning("Veuillez importer le fichier pour commencer.")
    st.stop()

# Chargement via la fonction dans utils
df_raw = utils.load_data(uploaded_files)

# Filtres de base
countries = ["Tous"] + sorted(df_raw["Country"].unique())
country_filter = st.sidebar.selectbox("Pays", countries)

min_date, max_date = df_raw["InvoiceDate"].min(), df_raw["InvoiceDate"].max()
date_range = st.sidebar.date_input("Période d'analyse", [min_date, max_date])

# Filtres avancés (regroupés pour nettoyer l'interface)
with st.sidebar.expander("Options avancées"):
    returns_mode = st.radio("Retours", ["Inclure", "Exclure", "Neutraliser"], index=1)
    
    # [NOUVEAU] Filtre Type Client
    customer_type = st.selectbox("Type de Client", ["Tous", "B2B (VIP)", "B2C (Standard)"])
    
    order_threshold = st.number_input(
        "Seuil de montant minimum par ligne (£)",
        min_value=0.0, value=0.0, step=10.0
    )

# Application des filtres
df = utils.apply_filters(df_raw, country_filter, date_range, returns_mode, order_threshold, customer_type)

if df.empty:
    st.error("Aucune donnée après application des filtres.")
    st.stop()

# RFM pré-calcul pour être réutilisé sur plusieurs pages
rfm_base = utils.compute_rfm(df)
rfm_scored = utils.score_rfm(rfm_base)

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["KPIs", "Cohortes", "RFM", "CLV", "Scénarios", "Export"]
)

filters_text = (
    f"Pays={country_filter} | "
    f"Période={date_range[0]}→{date_range[1]} | "
    f"Retours={returns_mode} | "
    f"Type Client={customer_type} | "
    f"Seuil={order_threshold}£"
)

# ---------------------------------------------------------
# Pages
# ---------------------------------------------------------

# ---------------- KPIs ----------------
if page == "KPIs":
    st.subheader("Vue d'ensemble – KPIs")
    
    # Calcul des KPIs via utils
    ca_total, n_clients, avg_order, north_star, avg_clv_emp = utils.compute_kpis(df)

    # Affichage en colonnes
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("CA total", f"{ca_total:,.0f} £")
    col2.metric("Clients actifs", n_clients)
    col3.metric("Panier moyen", f"{avg_order:,.2f} £")
    col4.metric("North Star (Repeat %)", f"{north_star:.1f} %", help="% clients > 1 achat")
    col5.metric("CLV Moyenne", f"{avg_clv_emp:,.0f} £")

    with st.expander("ℹ️ Aide – KPIs (définitions + exemples)"):
        with st.expander("ℹ️ Aide – KPIs"):
            st.markdown("""
            - **CA total** : somme du montant `Amount` sur la période.
            - **Clients actifs** : nombre de clients ayant acheté au moins une fois.
            - **Panier moyen** : CA / nombre de commandes.
            - **Repeat % (North Star)** : % de clients avec ≥2 achats.
            - **CLV empirique** : CA moyen généré par client.
            """)

    # [NOUVEAU] Graphique de tendance temporelle avec granularité variable
    st.subheader("Tendance des ventes")

    # Dictionnaire pour mapper le code (M) vers le nom affiché (Mois)
    format_map = {"M": "Mois", "Q": "Trimestre", "W": "Semaine"}
    granularity = st.selectbox(
        "Granularité temporelle", 
        options=["M", "Q", "W"], 
        format_func=lambda x: format_map[x]
    )

    # Resample pour grouper par Mois/Trimestre
    df_trend = df.set_index("InvoiceDate").resample(granularity)["Amount"].sum().reset_index()
    fig_trend = px.line(df_trend, x="InvoiceDate", y="Amount", title="Évolution du CA")
    fig_trend.add_annotation(
        text=filters_text,
        xref="paper", yref="paper",
        x=0, y=1.12,
        showarrow=False,
        align="left",
        font=dict(size=10, color="gray")
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.session_state["fig_trend"] = fig_trend #Sauvegarde pour le téléchargement
    png_trend = utils.export_plot_png(fig_trend, filters_text)
    st.download_button(
        "📥 Télécharger tendance des ventes",
        data=png_trend,
        file_name="tendance_vente.png",
        mime="image/png"
    )


# ---------------- Cohortes ----------------
elif page == "Cohortes":
    st.subheader("Analyse de cohortes")
    
    with st.expander("ℹ️ Aide – Cohortes"):
        st.markdown("""
        - **Cohorte** : clients acquis le même mois.
        - **Rétention M+X** : % encore actifs X mois après acquisition.
        - **Heatmap** : repère les mois où les cohortes décrochent.
        - **CohortIndex** : ancienneté (mois depuis la 1ʳᵉ commande).
        - **Box plot** : répartit les dépenses (valeur moyenne / clients “whales”).
        """)

    # 1. On récupère les données
    retention, rev_pivot = utils.compute_cohorts(df)
    
    # [NOUVEAU] On appelle ta nouvelle fonction pour avoir les détails (densité)
    df_density = utils.get_cohort_data_for_density(df)

    # 2. Sélecteur de Focus (Exigence : "possibilité de focus sur une cohorte")
    if not retention.empty:
        all_cohorts = sorted([str(c.date()) for c in retention.index], reverse=True)
        focus_cohort = st.selectbox("Focus sur une cohorte spécifique :", ["Toutes"] + all_cohorts)
    else:
        focus_cohort = "Toutes"

    # 3. Organisation en Onglets pour la clarté
    tab1, tab2 = st.tabs(["Rétention (Heatmap)", "Analyse de la Valeur (Densité)"])

    with tab1:
        if retention.empty:
            st.warning("Pas assez de données pour afficher les cohortes.")
        else:
            st.markdown("### Heatmap de Rétention")
            fig_ret = px.imshow(
                (retention * 100).round(1),
                labels=dict(x="Mois après acquisition", y="Cohorte", color="Rétention (%)"),
                aspect="auto", text_auto=True, color_continuous_scale="Blues"
            )
            st.session_state["fig_retention"] = fig_ret
            fig_ret.add_annotation(
                text=filters_text,
                xref="paper", yref="paper",
                x=0, y=1.12,
                showarrow=False,
                align="left",
                font=dict(size=10, color="gray")
            )
            st.plotly_chart(fig_ret, use_container_width=True)
            png_ret = utils.export_plot_png(fig_ret, filters_text)
            st.download_button(
                "📥 Télécharger heatmap cohortes",
                data=png_ret,
                file_name="cohortes_heatmap.png",
                mime="image/png"
            )

    with tab2:
        st.markdown("### Dynamique de dépense par ancienneté")
        
        if df_density.empty or df_density["Amount"].sum() == 0:
            st.warning("Aucune donnée disponible pour cette période / ce pays.")
            st.stop()
        
        elif focus_cohort == "Toutes":
            st.markdown("**Distribution des dépenses par âge (Vue Globale)**")
            st.info("💡 Ce graphique (Box Plot) montre la 'densité' : comment les dépenses sont réparties. La boîte contient 50% des clients.")
            
            # [NOUVEAU] Graphique de densité globale (Exigence : "courbes de densité")
            fig_dens = px.box(
                df_density, 
                x="CohortIndex", 
                y="Amount", 
                title="Densité de CA par ancienneté (Tous clients)",
                labels={"CohortIndex": "Mois après acquisition", "Amount": "Dépenses (£)"}
            )
            # Forcer l’axe X à toujours afficher 0 à 12
            fig_dens.update_xaxes(
                type="category",
                categoryorder="array",
                categoryarray=[str(i) for i in range(13)]
            )
            # On limite l’axe Y pour lisibilité (évite que les baleines écrasent tout)
            fig_dens.update_yaxes(range=[0, df_density["Amount"].quantile(0.95) * 1.5]) 
            st.session_state["fig_density"] = fig_dens
            fig_dens.add_annotation(
                text=filters_text,
                xref="paper", yref="paper",
                x=0, y=1.12,
                showarrow=False,
                align="left",
                font=dict(size=10, color="gray")
            )
            st.plotly_chart(fig_dens, use_container_width=True)
            png_dens = utils.export_plot_png(fig_dens, filters_text)
            st.download_button(
                "📥 Télécharger densité cohortes",
                data=png_dens,
                file_name="cohortes_densite.png",
                mime="image/png"
            )
            
        else:
            # [NOUVEAU] Vue Focus Cohorte
            st.markdown(f"**Analyse détaillée de la cohorte : {focus_cohort}**")
            
            # Filtrage sur la cohorte choisie
            cohort_date = pd.to_datetime(focus_cohort)
            df_focus = df_density[df_density["CohortMonth"] == cohort_date]
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**Tendance Moyenne**")
                # Courbe moyenne classique
                avg_trend = df_focus.groupby("CohortIndex")["Amount"].mean().reset_index()
                fig_line = px.line(avg_trend, x="CohortIndex", y="Amount", markers=True, 
                                   labels={"CohortIndex": "Mois", "Amount": "Panier Moyen (£)"})
                fig_line.update_xaxes(
                    type="category",
                    categoryorder="array",
                    categoryarray=[str(i) for i in range(13)]
                )
                fig_line.add_annotation(
                    text=filters_text,
                    xref="paper", yref="paper",
                    x=0, y=1.12,
                    showarrow=False,
                    align="left",
                    font=dict(size=10, color="gray")
                )
                st.plotly_chart(fig_line, use_container_width=True)
                png_line = utils.export_plot_png(fig_line, filters_text)
                st.download_button(
                    "📥 Télécharger tendance cohorte",
                    data=png_line,
                    file_name="cohorte_tendance.png",
                    mime="image/png"
                )
                
            with col_b:
                st.markdown("**Dispersion (Densité)**")
                # Densité spécifique à cette cohorte
                fig_box = px.box(df_focus, x="CohortIndex", y="Amount", 
                                 labels={"CohortIndex": "Mois", "Amount": "Dépenses (£)"})
                fig_box.update_yaxes(range=[0, df_focus["Amount"].quantile(0.98) * 1.2])
                fig_box.update_xaxes(
                    type="category",
                    categoryorder="array",
                    categoryarray=[str(i) for i in range(13)]
                )
                fig_box.add_annotation(
                    text=filters_text,
                    xref="paper", yref="paper",
                    x=0, y=1.12,
                    showarrow=False,
                    align="left",
                    font=dict(size=10, color="gray")
                )
                st.plotly_chart(fig_box, use_container_width=True)
                png_box = utils.export_plot_png(fig_box, filters_text)
                st.download_button(
                    "📥 Télécharger dispersion cohorte",
                    data=png_box,
                    file_name="cohorte_dispersion.png",
                    mime="image/png"
                )

# ---------------- RFM ----------------
elif page == "RFM":
    st.subheader("Segmentation RFM – Priorisation CRM")

    with st.expander("ℹ️ Aide – RFM"):
        st.markdown("""
        - **R (Recency)** : jours depuis le dernier achat.
        - **F (Frequency)** : nombre total de commandes.
        - **M (Monetary)** : montant total dépensé.
        - **Score RFM** : combinaison R+F+M → segment marketing.
        - **Panier moyen** : M / F.
        """)

    # [NOUVEAU] Slider pour estimer la Marge dans le tableau
    margin_pct = st.slider("Marge estimée (%) pour calcul rentabilité", 0, 100, 30) / 100

    # Table agrégée par segment
    if not rfm_scored.empty:
        # Agrégation pour le tableau récapitulatif
        seg_agg = rfm_scored.groupby("Segment").agg(
            n_clients=("CustomerID", "count"),
            CA_total=("Monetary", "sum"),
            Panier_moyen=("AvgBasket", "mean"), # [NOUVEAU] Utilisé depuis utils
            Action_recommandee=("Action", "first")
        ).reset_index()
        
        # Calculs dérivés
        seg_agg["Marge_estimee"] = seg_agg["CA_total"] * margin_pct
        seg_agg = seg_agg.sort_values("CA_total", ascending=False)

        st.markdown("### Vue agrégée par Segment")
        st.dataframe(seg_agg.style.format({
            "CA_total": "{:,.0f} £", 
            "Marge_estimee": "{:,.0f} £", 
            "Panier_moyen": "{:.2f} £"
        }))

        # Graphique Répartition
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_seg = px.bar(seg_agg, x="Segment", y="CA_total", text="n_clients", title="CA Total par Segment")
            st.session_state["fig_rfm_bar"] = fig_seg
            fig_seg.add_annotation(
                text=filters_text,
                xref="paper", yref="paper",
                x=0, y=1.12,
                showarrow=False,
                align="left",
                font=dict(size=10, color="gray")
            )
            st.plotly_chart(fig_seg, use_container_width=True)
            png_rfm_bar = utils.export_plot_png(fig_seg, filters_text)
            st.download_button(
                "📥 Télécharger RFM – CA par segment",
                data=png_rfm_bar,
                file_name="rfm_ca_segment.png",
                mime="image/png"
            )
        with col_g2:
            fig_pie = px.pie(seg_agg, values="n_clients", names="Segment", title="Répartition des Clients")
            st.session_state["fig_rfm_pie"] = fig_pie
            fig_pie.add_annotation(
                text=filters_text,
                xref="paper", yref="paper",
                x=0, y=1.12,
                showarrow=False,
                align="left",
                font=dict(size=10, color="gray")
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            png_rfm_pie = utils.export_plot_png(fig_pie, filters_text)
            st.download_button(
                "📥 Télécharger RFM – Répartition clients",
                data=png_rfm_pie,
                file_name="rfm_repartition.png",
                mime="image/png"
            )
            
    else:
        st.warning("Pas de données RFM.")


# ---------------- CLV ----------------
elif page == "CLV":
    st.subheader("Customer Lifetime Value (CLV)")
    
    with st.expander("ℹ️ Aide – CLV"):
        st.markdown("""
        - **CLV empirique** : CA moyen généré par client sur la période.
        - **CLV théorique** : dépend de la marge (m), rétention (r) et taux d’actualisation (d).
        - Formule : CLV = m·r / (1 + d − r).
        - Plus r ↑ → CLV ↑ ; plus d ↑ → CLV ↓.
        """)

    # ... (Le code CLV de base reste très similaire, juste appelé depuis utils si besoin)
    # Ici je garde ton code interface car il était spécifique
    clv_emp = utils.compute_kpis(df)[4] # On récupère juste la CLV emp
    st.metric("CLV moyenne empirique", f"{clv_emp:,.2f} £")

    st.markdown("### Calculateur CLV (Formule fermée)")
    
    col_a, col_b, col_c = st.columns(3)
    margin_input = col_a.number_input("Marge mensuelle (£/client)", value=15.0)
    r = col_b.slider("Rétention (r)", 0.0, 0.99, 0.75)
    d = col_c.slider("Taux d'actualisation (d)", 0.0, 1.0, 0.10)

    clv_res = utils.clv_formula(margin_input, r, d)
    st.metric("CLV Théorique", f"{clv_res:,.2f} £")
    
    with st.expander("ℹ️ Formule utilisée"):
        st.latex(r"CLV = \frac{m \cdot r}{1 + d - r}")


# ---------------- Scénarios ----------------
elif page == "Scénarios":
    st.subheader("Simulateur d'impact & Prise de décision")

    with st.expander("ℹ️ Aide – Scénarios"):
        st.markdown("""
        - Permet de tester l’impact : remise %, marge %, +rétention.
        - **Ciblage** : global, segment RFM ou cohorte.
        - Compare **Baseline vs Scénario** : CLV et impact CA.
        - Utile pour décider si une remise ou action CRM est rentable.
        """)
    st.markdown("---")

    # 1. CIBLAGE (Le fameux "Sélecteur cohorte cible ou segment")
    col_cible, col_params = st.columns([1, 2])
    
    with col_cible:
        st.header("1. Cible")
        target_mode = st.radio("Appliquer le scénario à :", ["Global (Tous)", "Par Segment RFM", "Par Cohorte"])
        
        df_target = df.copy() # Par défaut
        target_name = "Global"

        if target_mode == "Par Segment RFM":
            # On doit recalculer le RFM ici pour avoir les segments disponibles
            if 'Segment' not in rfm_scored.columns:
                 st.error("Veuillez d'abord aller sur l'onglet RFM pour générer les segments.")
                 st.stop()
            
            selected_seg = st.selectbox("Choisir le segment :", sorted(rfm_scored["Segment"].unique()))
            # Filtrer les ID clients du segment
            ids_segment = rfm_scored[rfm_scored["Segment"] == selected_seg]["CustomerID"]
            df_target = df[df["CustomerID"].isin(ids_segment)]
            target_name = f"Segment {selected_seg}"

        elif target_mode == "Par Cohorte":
            # Récupérer les mois de cohorte
            retention_check, _ = utils.compute_cohorts(df)
            cohorts_list = sorted([str(c.date()) for c in retention_check.index], reverse=True)
            selected_cohort = st.selectbox("Choisir la cohorte :", cohorts_list)
            
            # Recalcul rapide pour trouver les ID de cette cohorte
            # Note : Idéalement on aurait une fonction optimisée dans utils, mais on filtre ici
            first_purch = df.groupby("CustomerID")["InvoiceDate"].min().dt.to_period("M").dt.to_timestamp()
            ids_cohort = first_purch[first_purch == pd.to_datetime(selected_cohort)].index
            df_target = df[df["CustomerID"].isin(ids_cohort)]
            target_name = f"Cohorte {selected_cohort}"
        
        n_target = df_target["CustomerID"].nunique()
        st.info(f"Population cible : **{n_target} clients**")

    # 2. PARAMÈTRES (Distinction Marge / Remise)
    with col_params:
        st.header("2. Hypothèses")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Situation Actuelle (Baseline)**")
            base_margin_pct = st.number_input("Marge Brute actuelle (%)", 30.0, 100.0, 40.0, step=5.0) / 100
            base_r = st.slider("Rétention actuelle (r)", 0.0, 0.99, 0.60)
            base_d = st.number_input("Taux d'actualisation (d)", 0.0, 0.5, 0.10)
        
        with c2:
            st.markdown("**Scénario (Action)**")
            # [NOUVEAU] Slider Remise distinct
            remise_pct = st.slider("Remise accordée (%)", 0.0, 50.0, 0.0, help="Diminue la marge directe")
            impact_retention = st.slider("Gain espéré de rétention (+pts)", 0.0, 20.0, 5.0) / 100
            
    st.markdown("---")

    # 3. CALCULS ET RÉSULTATS
    if n_target > 0:
        # Calcul de la marge mensuelle moyenne (m) pour CETTE cible
        m_base_val = (df_target["Amount"].sum() / n_target) * base_margin_pct # Simplification CLV empirique * marge
        # Note : Pour être très précis, m devrait être mensuel. 
        # Ici on prend une approx basée sur le panier moyen total / durée vie, ajustons :
        # On va utiliser le panier moyen * fréquence mensuelle approx
        
        # Méthode robuste via utils
        # On recalcule les KPI basiques pour la cible
        _, _, panier_target, _, _ = utils.compute_kpis(df_target)
        # Frequence d'achat mensuelle moyenne (approx) : 
        # Disons qu'un client achète F fois sur T mois. F/T.
        # Pour simplifier l'exercice académique, on fixe m = Panier Moyen * Marge * Freq (arbitraire 1 achat/mois pour l'exemple ou calculé)
        # On va utiliser le panier moyen comme base de 'm' par transaction
        
        m_monetary_base = panier_target * base_margin_pct
        
        # Scénario
        effective_margin_pct = base_margin_pct * (1 - remise_pct/100)
        m_monetary_scen = panier_target * effective_margin_pct
        
        scen_r = min(0.99, base_r + impact_retention)
        
        # CLV (Formule fermée)
        clv_base = utils.clv_formula(m_monetary_base, base_r, base_d)
        clv_scen = utils.clv_formula(m_monetary_scen, scen_r, base_d)
        
        delta_clv = clv_scen - clv_base
        impact_ca_total = delta_clv * n_target

        st.subheader(f"Résultats pour : {target_name}")
        
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("CLV Baseline", f"{clv_base:.2f} £")
        col_res2.metric("CLV Scénario", f"{clv_scen:.2f} £", delta=f"{delta_clv:.2f} £")
        col_res3.metric("Impact Total (Est.)", f"{impact_ca_total:,.0f} £", help="Delta CLV * Nombre clients cible")

        # Analyse graphique
        st.markdown("#### Pourquoi ça varie ?")
        st.caption(f"Effet croisé : La remise baisse la marge de **{remise_pct}%**, mais la rétention augmente de **{impact_retention*100:.0f} points**.")
        
        # Graphique en cascade (Waterfall) simulé ou Bar chart
        fig_comp = px.bar(
            x=["Baseline", "Scénario"], 
            y=[clv_base, clv_scen], 
            color=["Baseline", "Scénario"],
            title="Comparaison de la Valeur Vie Client (CLV)",
            text_auto=".2f"
        )
        st.session_state["fig_scenario"] = fig_comp
        fig_comp.add_annotation(
            text=filters_text,
            xref="paper", yref="paper",
            x=0, y=1.12,
            showarrow=False,
            align="left",
            font=dict(size=10, color="gray")
        )
        st.plotly_chart(fig_comp, use_container_width=True)
        png_scenario = utils.export_plot_png(fig_comp, filters_text)
        st.download_button(
            "📥 Télécharger comparaison CLV",
            data=png_scenario,
            file_name="scenario_clv.png",
            mime="image/png"
        )
        
    else:
        st.warning("Aucun client dans la cible sélectionnée.")


# ---------------- Export ----------------
elif page == "Export":
    st.subheader("Plan d'action – Export des données")

    with st.expander("ℹ️ Aide – Export"):
        st.markdown("""
        - **Dataset filtré** : transactions après application des filtres.
        - **Liste RFM** : CustomerID + segment + métriques clés.
        """)

    st.markdown("### Export du dataset filtré")
    csv_full = df.to_csv(index=False).encode("utf-8")
    st.download_button("Télécharger le dataset filtré (CSV)", csv_full, "dataset_filtre.csv", "text/csv")

    st.markdown("### Export de la liste activable (RFM)")
    if not rfm_scored.empty:
        # Préparation de l'export avec les métriques utiles
        activable = rfm_scored[["CustomerID", "Segment", "Action", "Recency", "Frequency", "Monetary", "AvgBasket"]]
        csv_act = activable.to_csv(index=False).encode("utf-8")
        
        st.download_button("Télécharger la liste RFM (CSV)", csv_act, "liste_activable_rfm.csv", "text/csv")
        st.dataframe(activable.head())