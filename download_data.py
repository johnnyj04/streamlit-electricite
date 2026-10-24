from utils.loader import construire

mensuel, qualite = construire()
print("Terminé :", len(mensuel), "lignes mensuelles,", qualite["regions"], "régions,",
      qualite["debut"], "->", qualite["fin"])
