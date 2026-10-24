import os

import pandas as pd
import streamlit as st

from utils import charts, loader

st.set_page_config(page_title="Électricité et CO₂ en France", layout="wide")

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_efrei.png")
NOM = "Johnny Jin"
PROGRAMME = "Cycle ingénieur — Data Engineering"
ANNEE = "M1"
EMAIL = "johnny.jin@g.efrei.net"
LINKEDIN = "https://www.linkedin.com/in/johnnyjin/"
GITHUB = "https://github.com/johnnyj04"
COURS = "Data Analysis & Visualization"
PROF = "Prof. Mano Mathew"
PROF_EMAIL = "mano.mathew@efrei.fr"
PROF_LINKEDIN = "https://www.linkedin.com/in/manomathew/"

FILIERES = list(loader.FILIERES)
INDICATEURS = {"Intensité CO₂ (g CO₂e/kWh)": "intensite",
               "Part bas carbone (%)": "bas_carbone",
               "Part renouvelable (%)": "renouvelable"}


@st.cache_data(show_spinner="Chargement des données...")
def charger():
    return loader.charger_donnees()


@st.cache_data(show_spinner=False)
def carte_geojson():
    return charts.charger_carte()


def totaux(d, facteurs=None):
    return loader.ajouter_indicateurs(d[FILIERES].sum().to_frame().T, facteurs).iloc[0]


def par_region_de(d):
    return loader.ajouter_indicateurs(d.groupby(["code", "region"], as_index=False)[FILIERES].sum())


try:
    mensuel, qualite = charger()
except Exception as e:
    st.error(f"Impossible de charger les données : {e}")
    st.stop()

if os.path.exists(LOGO):
    st.sidebar.image(LOGO)
st.sidebar.markdown(f"**{NOM}**  \n{PROGRAMME}  \n{ANNEE}")
st.sidebar.markdown(f"[{EMAIL}](mailto:{EMAIL})  \n[LinkedIn]({LINKEDIN})")
if GITHUB:
    st.sidebar.markdown(f"[GitHub]({GITHUB})")
st.sidebar.markdown(f"**Cours :** {COURS}  \n**Projet proposé par :** {PROF} "
                    f"([{PROF_EMAIL}](mailto:{PROF_EMAIL}), [LinkedIn]({PROF_LINKEDIN}))")
st.sidebar.divider()

st.sidebar.header("Filtres")
regions_dispo = sorted(mensuel["region"].unique())
regions = st.sidebar.multiselect("Régions", regions_dispo, default=regions_dispo,
                                 help="Garde toutes les régions pour la vue nationale.")
debut_min, fin_max = mensuel["mois"].min().date(), mensuel["mois"].max().date()
periode = st.sidebar.date_input("Période", value=(debut_min, fin_max),
                                min_value=debut_min, max_value=fin_max,
                                help="Choisis une date de début et une date de fin.")
libelle = st.sidebar.selectbox("Variable à afficher", list(INDICATEURS),
                               help="Change les graphiques, la carte et la comparaison avant / après.")
col = INDICATEURS[libelle]
nom_court = libelle.split(" (")[0]
nom_bas = nom_court[0].lower() + nom_court[1:]

st.sidebar.subheader("Comparaison avant / après")
mois_par_annee = mensuel.groupby(mensuel["mois"].dt.year)["mois"].nunique()
annees = [int(a) for a in mois_par_annee[mois_par_annee == 12].index]
avant = st.sidebar.selectbox("Année « avant »", annees, index=0, help="Seules les années complètes sont proposées.")
apres = st.sidebar.selectbox("Année « après »", annees, index=len(annees) - 1)

if not regions or len(periode) != 2:
    st.info("Choisis au moins une région et une date de début et de fin.")
    st.stop()

df = mensuel[mensuel["region"].isin(regions)
             & (mensuel["mois"] >= pd.Timestamp(periode[0]).to_period("M").to_timestamp())
             & (mensuel["mois"] <= pd.Timestamp(periode[1]))]
if df.empty:
    st.warning("Aucune donnée pour cette sélection.")
    st.stop()

par_region = par_region_de(df)
total = totaux(df)
selection = loader.ajouter_indicateurs(df.groupby("mois", as_index=False)[FILIERES].sum())

st.title("L'électricité française est-elle de moins en moins carbonée ?")
st.caption("Source : RTE, éCO2mix régional consolidé et définitif (ODRÉ / data.gouv.fr), "
           "Licence Ouverte 2.0.")

st.header("1. Accroche")
st.markdown("**Un kWh n'a pas le même impact carbone selon la façon dont il est produit.** "
            "Électrifier les transports ou le chauffage n'aide le climat que si l'électricité "
            "est peu carbonée.")
st.markdown("**Public visé :** étudiants, analystes et citoyens intéressés par la transition énergétique.")
st.markdown("**Questions auxquelles répond ce dashboard :**\n"
            "1. L'électricité produite en France est-elle de moins en moins carbonée ?\n"
            "2. Quelles régions sont les plus propres, et lesquelles le sont le moins ?\n"
            "3. Qu'est-ce qui explique les écarts : le mélange des sources de production ?")

st.header("2. Contexte")
st.markdown("**Chaque région produit son électricité avec un mélange différent.** "
            f"Les données couvrent {qualite['regions']} régions de métropole, de {qualite['debut'][:7]} "
            f"à {qualite['fin'][:7]}. L'intensité CO₂ n'est pas dans le fichier : elle est **estimée** "
            "à partir de la production de chaque filière et de facteurs d'émission du GIEC.")
with st.expander("Comment l'intensité CO₂ est-elle calculée ?"):
    st.markdown("Intensité = somme (production de chaque filière × facteur d'émission) / production totale.")
    st.table(pd.DataFrame({"Filière": [loader.FILIERES[f] for f in FILIERES],
                           "Facteur (g CO₂e/kWh)": [loader.FACTEURS[f] for f in FILIERES]}))

st.subheader("Chiffres clés de la sélection")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Intensité CO₂", f"{total['intensite']:.0f} g/kWh",
          help="Grammes de CO₂ équivalent émis par kWh produit (estimation).")
c2.metric("Part bas carbone", f"{total['bas_carbone']:.1f} %",
          help="Nucléaire + hydraulique + éolien + solaire + bioénergies, en % de la production.")
c3.metric("Part renouvelable", f"{total['renouvelable']:.1f} %",
          help="Hydraulique + éolien + solaire + bioénergies, en % de la production.")
c4.metric("Production (période)", f"{total['total'] / 1e6:.1f} TWh",
          help="Production totale des régions et de la période choisies.")
charbon = totaux(df, {**loader.FACTEURS, "thermique": loader.FACTEUR_CHARBON})
st.caption(f"Incertitude : si tout le thermique fossile était du charbon ({loader.FACTEUR_CHARBON} g/kWh) "
           f"au lieu de gaz ({loader.FACTEURS['thermique']} g/kWh), l'intensité serait de "
           f"{charbon['intensite']:.0f} g/kWh au lieu de {total['intensite']:.0f}.")

st.header("3. Enseignements clés")

st.subheader("3a. Comment ça évolue dans le temps ?")
bas = selection.loc[selection[col].idxmin()]
haut = selection.loc[selection[col].idxmax()]
st.markdown(f"**Sur la période, {nom_bas} varie de {bas[col]:.1f} ({bas['mois']:%m/%Y}) "
            f"à {haut[col]:.1f} ({haut['mois']:%m/%Y}).**")
charts.afficher(charts.courbe(df, selection, col, libelle),
                "Lignes mensuelles : une ligne colorée par région (voir la légende), une ligne noire épaisse pour l'ensemble "
                "de la sélection, et une ligne pointillée pour la moyenne de la période.")

st.subheader("3b. Avant / après")
d_avant = mensuel[(mensuel["mois"].dt.year == avant) & mensuel["region"].isin(regions)]
d_apres = mensuel[(mensuel["mois"].dt.year == apres) & mensuel["region"].isin(regions)]
t_avant, t_apres = totaux(d_avant), totaux(d_apres)
a, b = t_avant[col], t_apres[col]


def formater(v):
    return f"{v:.0f} g/kWh" if col == "intensite" else f"{v:.1f} %"


if col == "intensite":
    ecart = f"{(b / a - 1) * 100:+.0f} %"
    couleur = "inverse"
else:
    ecart = f"{b - a:+.1f} pts"
    couleur = "normal"
tab = (par_region_de(d_avant)[["region", col]].rename(columns={col: "avant"})
       .merge(par_region_de(d_apres)[["region", col]].rename(columns={col: "apres"}), on="region"))
tab["changement"] = (tab["apres"] - tab["avant"]).abs()
plus = tab.sort_values("changement").iloc[-1]
st.markdown(f"**Entre {avant} et {apres}, {nom_bas} passe de {formater(a)} à {formater(b)} "
            f"({ecart}). La région qui change le plus est {plus['region']} : "
            f"de {plus['avant']:.0f} à {plus['apres']:.0f}.**")
m1, m2, m3 = st.columns(3)
m1.metric(f"{nom_court} en {avant}", formater(a))
m2.metric(f"{nom_court} en {apres}", formater(b), ecart, delta_color=couleur)
m3.metric(f"Production en {apres}", f"{t_apres['total'] / 1e6:.1f} TWh",
          f"{(t_apres['total'] / t_avant['total'] - 1) * 100:+.1f} % vs {avant}", delta_color="off")
charts.afficher(charts.avant_apres(tab, col, libelle, avant, apres),
                f"Barres groupées : pour chaque région, la valeur de {nom_bas} en {avant} (gris) "
                f"et en {apres} (orange). Les années complètes sont comparées, sans tenir compte de la période choisie.")

st.subheader("3c. Où ? Comparer les régions")
meilleure = par_region.sort_values("intensite").iloc[0]
pire = par_region.sort_values("intensite").iloc[-1]
st.markdown(f"**Sur la période, l'écart entre régions va de {meilleure['intensite']:.0f} g/kWh "
            f"({meilleure['region']}) à {pire['intensite']:.0f} g/kWh ({pire['region']}).**")
gauche, droite = st.columns(2)
with gauche:
    charts.afficher(charts.barres(par_region, col, libelle, total[col]),
                    "Barres horizontales classant les régions de la plus faible à la plus forte valeur, "
                    "avec une ligne pointillée pour la moyenne de la sélection.")
with droite:
    geo = carte_geojson()
    if geo:
        charts.afficher(charts.carte(par_region, col, libelle, geo),
                        "Carte de France par région, colorée selon la valeur de l'indicateur.")
    else:
        st.warning("Les contours des régions n'ont pas pu être chargés : la carte est masquée.")

st.subheader("3d. Pourquoi ? Le mélange de sources")
st.markdown("**Les écarts viennent du mélange : plus une région produit avec du thermique fossile, "
            "plus son intensité est élevée (c'est la conséquence directe de la méthode de calcul).**")
charts.afficher(charts.petits_multiples(df),
                "Petits multiples : un graphique par région, avec des barres empilées par année montrant "
                "la part de chaque filière dans la production. 2026 est une année incomplète.")

st.header("Qualité des données")
st.markdown("**Les données sont presque complètes : les valeurs manquantes ne concernent que le nucléaire.**")
q1, q2, q3 = st.columns(3)
q1.metric("Lignes du fichier", f"{qualite['lignes']:,}")
q2.metric("Doublons supprimés", f"{qualite['doublons']:,}")
q3.metric("Valeurs négatives mises à 0", f"{qualite['negatifs']:,}",
          help="Petites valeurs négatives (consommation propre des installations), mises à 0.")
manquants = pd.DataFrame({"Filière": list(qualite["manquants"]),
                          "Valeurs manquantes (%)": list(qualite["manquants"].values())})
controles = pd.DataFrame({
    "Contrôle": ["12 régions présentes", "Même nombre de mois pour chaque région",
                 "Aucune valeur négative après nettoyage", "Production totale positive chaque mois"],
    "Résultat": ["OK" if qualite["regions"] == 12 else f"{qualite['regions']} régions",
                 "OK" if len(set(qualite["mois_par_region"].values())) == 1 else "Mois manquants",
                 "OK" if (mensuel[FILIERES] >= 0).all().all() else "À vérifier",
                 "OK" if (mensuel["total"] > 0).all() else "À vérifier"]})
x, y = st.columns(2)
x.dataframe(manquants, hide_index=True)
y.dataframe(controles, hide_index=True)
sans_centrale = [r for r, v in qualite["nucleaire_manquant_par_region"].items() if v > 50]
st.info("Les valeurs manquantes du nucléaire correspondent aux régions sans centrale ("
        + ", ".join(sans_centrale) + "). Elles sont remplacées par 0, car la production y est nulle.")

st.header("Limites")
st.markdown("- L'intensité CO₂ est **estimée** (facteurs moyens), pas mesurée.\n"
            "- Le thermique fossile (gaz, charbon, fioul) n'est pas détaillé : on suppose du gaz "
            "(voir la note d'incertitude sous les chiffres clés).\n"
            "- On regarde la production **dans** la région : les échanges avec les autres régions "
            "et pays sont ignorés.\n"
            "- Les données récentes sont consolidées et peuvent encore changer. 2026 est incomplète.\n"
            "- Ce dashboard décrit : il ne prouve pas la cause d'une évolution.\n"
            "- Éthique : ce sont des données agrégées du réseau électrique, sans donnée personnelle.")

st.header("4. Implications et prochaines étapes")
st.markdown("**Réduire le thermique fossile est le levier principal pour baisser l'intensité CO₂.**")
st.markdown(f"- Région à suivre en priorité sur la période : {pire['region']} "
            f"({pire['intensite']:.0f} g/kWh).\n"
            "- Suivre ces indicateurs chaque année pour voir si l'écart entre régions se réduit.\n"
            "- Prochaines étapes : prendre en compte les échanges entre régions, et séparer "
            "gaz, charbon et fioul.")
