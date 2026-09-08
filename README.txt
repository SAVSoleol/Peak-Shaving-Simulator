PEAK SHAVING SIMULATOR V1

Base
----
Développé à partir du Battery Sizer existant, en réutilisant loaders.py.

Fonctionnement
--------------
- Courbe import/export : kW ou kWh détectés automatiquement depuis les en-têtes.
- Batterie : une configuration à la fois.
- Recharge : PV + réseau autorisé.
- Recharge réseau : limitée pour ne pas dépasser le seuil de puissance cible.
- Réserve Peak Shaving : SOC cible que la batterie cherche à restaurer.
- SOC minimum : limite physique de décharge.
- Recherche automatique du seuil minimal soutenable sur toute la période.
- Groupe E : 5.10 CHF/kW/mois prérempli.
- Facturation : bande annuelle par défaut, mode maximum mensuel disponible.
- Affichage :
  * pointe avant / après
  * seuil soutenable
  * réduction garantie
  * économie annuelle
  * recharge réseau/PV
  * courbe annuelle
  * journée critique
  * SOC
  * top 10 des pointes
  * pointes mensuelles

Lancement
---------
pip install streamlit pandas numpy plotly openpyxl
streamlit run app_peak_shaving.py

Fichier de test fourni par l'utilisateur
----------------------------------------
Mivelaz_Bois_2025_Import_Export_kW(3).xlsx

V1.1 : identification de l'intervalle réellement limitant, diagnostic kW/kWh, correction du tableau mensuel en bande annuelle.
