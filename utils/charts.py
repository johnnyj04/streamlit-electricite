import json
import os

import plotly.colors as pc
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from utils.loader import DOSSIER, FILIERES, URL_CARTE

COULEURS = {"Nucléaire": "#CC79A7", "Hydraulique": "#0072B2", "Éolien": "#56B4E9",
            "Solaire": "#E69F00", "Bioénergies": "#009E73", "Thermique fossile": "#4D4D4D"}


COULEURS_REGIONS = {
    "Auvergne-Rhône-Alpes": "#1f77b4", "Bourgogne-Franche-Comté": "#ff7f0e", "Bretagne": "#2ca02c",
    "Centre-Val de Loire": "#d62728", "Grand Est": "#9467bd", "Hauts-de-France": "#8c564b",
    "Normandie": "#e377c2", "Nouvelle-Aquitaine": "#bcbd22", "Occitanie": "#17becf",
    "Pays de la Loire": "#0b5394", "Provence-Alpes-Côte d'Azur": "#f1a20c", "Île-de-France": "#7b1fa2"}


def echelle(col):
    return "YlOrRd" if col == "intensite" else "YlGn"


def afficher(fig, description):
    fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=50, b=10),
                      font=dict(size=13))
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Description du graphique : " + description)


def courbe(df, selection, col, libelle):
    fig = go.Figure()
    for nom, g in df.groupby("region"):
        fig.add_trace(go.Scatter(x=g["mois"], y=g[col], mode="lines", name=nom,
                                 line=dict(width=1.5, color=COULEURS_REGIONS.get(nom, "#888888")),
                                 hovertemplate="%{fullData.name}<br>%{x|%b %Y} : %{y:.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=selection["mois"], y=selection[col], mode="lines",
                             name="Sélection (toutes les régions choisies)",
                             line=dict(width=3, color="black"),
                             hovertemplate="Sélection<br>%{x|%b %Y} : %{y:.1f}<extra></extra>"))
    ref = selection[col].mean()
    fig.add_hline(y=ref, line_dash="dash", line_color="#D55E00", annotation_text=f"Moyenne de la période : {ref:.1f}",
                  annotation_position="top left", annotation_bgcolor="white")
    fig.update_layout(title=f"Évolution mensuelle : {libelle}", xaxis_title="Mois", yaxis_title=libelle,
                      legend=dict(orientation="h", y=-0.25))
    return fig


def avant_apres(tableau, col, libelle, avant, apres):
    long = tableau.melt(id_vars="region", value_vars=["avant", "apres"], var_name="moment", value_name="valeur")
    long["moment"] = long["moment"].map({"avant": f"Avant ({avant})", "apres": f"Après ({apres})"})
    ordre = tableau.sort_values("avant", ascending=False)["region"].tolist()
    fig = px.bar(long, x="region", y="valeur", color="moment", barmode="group", text_auto=".0f",
                 category_orders={"region": ordre},
                 color_discrete_map={f"Avant ({avant})": "#9AA3AA", f"Après ({apres})": "#D55E00"},
                 labels={"valeur": libelle, "region": "Région", "moment": "Année"},
                 title=f"{libelle} : {avant} contre {apres}, par région")
    fig.update_traces(hovertemplate="%{x}<br>%{fullData.name} : %{y:.1f}<extra></extra>")
    fig.update_xaxes(tickangle=-35)
    return fig


def barres(df, col, libelle, ref):
    d = df.sort_values(col)
    fig = px.bar(d, x=col, y="region", orientation="h", color=col, color_continuous_scale=echelle(col),
                 labels={col: libelle, "region": "Région"},
                 title=f"Classement des régions : {libelle}")
    fig.update_layout(coloraxis_showscale=False)
    fig.add_vline(x=ref, line_dash="dash", line_color="black",
                  annotation_text=f"Moyenne : {ref:.1f}", annotation_position="top")
    return fig


def charger_carte():
    chemin = os.path.join(DOSSIER, "data", "regions.geojson")
    try:
        if not os.path.exists(chemin):
            r = requests.get(URL_CARTE, timeout=60)
            r.raise_for_status()
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(r.text)
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def contour(geometrie):
    if geometrie["type"] == "MultiPolygon":
        polygones = geometrie["coordinates"]
    else:
        polygones = [geometrie["coordinates"]]
    xs, ys = [], []
    for polygone in polygones:
        for lon, lat in polygone[0]:
            xs.append(lon)
            ys.append(lat)
        xs.append(None)
        ys.append(None)
    return xs, ys


def carte(df, col, libelle, geojson):
    valeurs = df.set_index("code")[col]
    vmin, vmax = valeurs.min(), valeurs.max()
    fig = go.Figure()
    for region in geojson["features"]:
        code = region["properties"]["code"]
        nom = region["properties"]["nom"]
        xs, ys = contour(region["geometry"])
        if code in valeurs.index:
            t = 0.5 if vmax == vmin else (valeurs[code] - vmin) / (vmax - vmin)
            couleur = pc.sample_colorscale(echelle(col), [t])[0]
            texte = f"{nom}<br>{libelle} : {valeurs[code]:.1f}"
        else:
            couleur = "#E6E6E6"
            texte = f"{nom}<br>non sélectionnée ou non couverte"
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=couleur,
                                 line=dict(color="white", width=1), text=texte, hoverinfo="text",
                                 hoveron="fills", showlegend=False))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(colorscale=echelle(col), cmin=vmin, cmax=vmax, color=[vmin],
                                         showscale=True, colorbar=dict(title=libelle, thickness=12))))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1.45)
    fig.update_layout(title=f"Carte : {libelle}", height=500)
    return fig


def petits_multiples(df):
    d = df.assign(annee=df["mois"].dt.year.astype(str))
    par_annee = d.groupby(["annee", "region"], as_index=False)[list(FILIERES)].sum()
    long = par_annee.melt(id_vars=["annee", "region"], var_name="filiere", value_name="mwh")
    long["part"] = long["mwh"] / long.groupby(["annee", "region"])["mwh"].transform("sum") * 100
    long["filiere"] = long["filiere"].map(FILIERES)
    lignes = max(1, -(-long["region"].nunique() // 4))
    fig = px.bar(long, x="annee", y="part", color="filiere", facet_col="region", facet_col_wrap=4,
                 color_discrete_map=COULEURS, category_orders={"filiere": list(COULEURS)},
                 labels={"part": "Part de la production (%)", "annee": "Année", "filiere": "Filière"},
                 title="Mélange de production par région et par année (% de la production)")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font_size=11))
    fig.update_xaxes(tickangle=-90, tickfont_size=9, title_text="")
    fig.update_yaxes(range=[0, 100], title_text="")
    fig.update_traces(hovertemplate="%{x} : %{fullData.name} %{y:.1f} %<extra></extra>")
    fig.update_layout(height=230 * lignes + 120, legend=dict(orientation="h", y=-0.12))
    return fig
