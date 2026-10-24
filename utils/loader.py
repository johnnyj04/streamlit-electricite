import json
import os

import pandas as pd
import requests

DOSSIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_CSV = os.path.join(DOSSIER, "data", "eco2mix.csv")
CHEMIN_MENSUEL = os.path.join(DOSSIER, "data", "mensuel.csv")
CHEMIN_QUALITE = os.path.join(DOSSIER, "data", "qualite.json")
URLS = [
    "https://www.data.gouv.fr/api/1/datasets/r/4c308634-d76e-40b0-a777-ab99a8871564",
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "eco2mix-regional-cons-def/exports/csv?lang=fr&use_labels=false&delimiter=%3B",
]
URL_CARTE = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
             "master/regions-version-simplifiee.geojson")

FILIERES = {"nucleaire": "Nucléaire", "hydraulique": "Hydraulique", "eolien": "Éolien",
            "solaire": "Solaire", "bioenergies": "Bioénergies", "thermique": "Thermique fossile"}
RENOUVELABLES = ["hydraulique", "eolien", "solaire", "bioenergies"]
BAS_CARBONE = ["nucleaire"] + RENOUVELABLES

FACTEUR_CHARBON = 820
FACTEURS = {"nucleaire": 12, "hydraulique": 24, "eolien": 11,
            "solaire": 48, "bioenergies": 230, "thermique": 490}

RENOMMER = {"code insee région": "code_insee_region", "région": "libelle_region",
            "date": "date", "date - heure": "date_heure",
            "thermique (mw)": "thermique", "nucléaire (mw)": "nucleaire",
            "eolien (mw)": "eolien", "solaire (mw)": "solaire",
            "hydraulique (mw)": "hydraulique", "bioénergies (mw)": "bioenergies"}
for _nom in ["code_insee_region", "libelle_region", "date", "date_heure"] + list(FILIERES):
    RENOMMER[_nom] = _nom


def telecharger_donnees():
    if os.path.exists(CHEMIN_CSV) and os.path.getsize(CHEMIN_CSV) > 0:
        return CHEMIN_CSV
    os.makedirs(os.path.dirname(CHEMIN_CSV), exist_ok=True)
    erreur = None
    for url in URLS:
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(CHEMIN_CSV, "wb") as f:
                    for morceau in r.iter_content(1024 * 1024):
                        f.write(morceau)
            return CHEMIN_CSV
        except requests.RequestException as e:
            erreur = e
    raise RuntimeError(f"Téléchargement impossible : {erreur}")


def lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig") as f:
        entete = f.readline()
    sep = ";" if entete.count(";") >= entete.count(",") else ","
    df = pd.read_csv(chemin, sep=sep, encoding="utf-8-sig", low_memory=False,
                     usecols=lambda c: c.strip().lower() in RENOMMER)
    df.columns = [RENOMMER[c.strip().lower()] for c in df.columns]
    return df


def ajouter_indicateurs(df, facteurs=None):
    facteurs = facteurs or FACTEURS
    df = df.copy()
    df["total"] = df[list(FILIERES)].sum(axis=1)
    df["co2_t"] = sum(df[f] * facteurs[f] for f in FILIERES) / 1000
    total = df["total"].where(df["total"] > 0)
    df["intensite"] = df["co2_t"] / total * 1000
    df["bas_carbone"] = df[BAS_CARBONE].sum(axis=1) / total * 100
    df["renouvelable"] = df[RENOUVELABLES].sum(axis=1) / total * 100
    return df


def preparer(brut):
    df = brut.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    df["code"] = df["code_insee_region"].astype(str).str.replace(r"\.0$", "", regex=True)

    qualite = {"lignes": len(df)}
    doublons = df.duplicated(["code", "date_heure"])
    qualite["doublons"] = int(doublons.sum())
    df = df[~doublons]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    for c in FILIERES:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    qualite["manquants"] = {FILIERES[c]: round(df[c].isna().mean() * 100, 2) for c in FILIERES}
    qualite["nucleaire_manquant_par_region"] = (
        df.groupby("libelle_region")["nucleaire"].apply(lambda x: round(x.isna().mean() * 100, 1)).to_dict())
    qualite["negatifs"] = int(sum((df[c] < 0).sum() for c in FILIERES))
    for c in FILIERES:
        df[c] = df[c].clip(lower=0).fillna(0) * 0.5

    df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
    mensuel = (df.groupby(["mois", "code", "libelle_region"], as_index=False)[list(FILIERES)].sum()
               .rename(columns={"libelle_region": "region"}))
    mensuel = ajouter_indicateurs(mensuel)
    qualite["regions"] = int(mensuel["region"].nunique())
    qualite["debut"] = str(mensuel["mois"].min().date())
    qualite["fin"] = str(mensuel["mois"].max().date())
    qualite["mois_par_region"] = mensuel.groupby("region")["mois"].nunique().to_dict()
    return mensuel, qualite


def construire(chemin_csv=None):
    chemin_csv = chemin_csv or telecharger_donnees()
    mensuel, qualite = preparer(lire_csv(chemin_csv))
    mensuel.to_csv(CHEMIN_MENSUEL, index=False)
    with open(CHEMIN_QUALITE, "w", encoding="utf-8") as f:
        json.dump(qualite, f, ensure_ascii=False, indent=2, default=lambda o: o.item())
    return mensuel, qualite


def charger_donnees():
    if os.path.exists(CHEMIN_MENSUEL) and os.path.exists(CHEMIN_QUALITE):
        mensuel = pd.read_csv(CHEMIN_MENSUEL, parse_dates=["mois"], dtype={"code": str})
        with open(CHEMIN_QUALITE, encoding="utf-8") as f:
            qualite = json.load(f)
        return mensuel, qualite
    return construire()
