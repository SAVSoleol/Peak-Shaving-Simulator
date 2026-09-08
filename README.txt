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

V1.2 :
- analyse du premier seuil inférieur impossible ;
- identification de la vraie cause d'échec (kW, kWh, les deux, ou séquence de pointes) ;
- affichage batterie dans le résumé ;
- coût annuel de puissance avant/après ;
- graphique de la journée du premier échec ;
- tableau mensuel forcé sur janvier-décembre.

V1.3 : correction du titre rogné en haut et hauteur du tableau mensuel ajustée pour afficher les 12 mois sans masquer novembre/décembre.

V1.4 :
- code couleur cohérent : négatif/échec = rouge, positif = vert, information neutre = bleu ;
- suppression du delta rouge trompeur sur l'économie ;
- tableau mensuel limité aux périodes réellement présentes dans le fichier ;
- diagnostic séparé en rouge (échec), bleu (diagnostic) et vert (action possible).

V1.5 :
- rapport PDF 3 pages intégré ;
- charte graphique calquée sur le rapport Battery Sizer Soleol ;
- page 1 synthèse / coûts / batterie ;
- page 2 graphiques et diagnostic du premier seuil impossible ;
- page 3 top 10, pointes mensuelles et formule d'économie ;
- bouton de téléchargement PDF dans Streamlit.

V1.6 :
- ajout de l'image panoramique avec fondu blanc dans l'en-tête page 1 ;
- fichier image à conserver sous le nom exact : rapport_header_montagnes.png ;
- page 1 rapprochée de la maquette : titre Peak Shaving + Synthèse de l'étude,
  6 KPI principaux, grande carte économie, paramètres techniques plus petits ;
- tailles de police et hiérarchie visuelle revues.

V1.7 :
- textes secondaires des KPI page 1 agrandis ;
- conclusion page 1 complétée par la cause limitante et l'orientation kWh/kW ;
- graphiques page 2 agrandis et rendus plus lisibles ;
- premier seuil impossible présenté sous forme de lignes structurées ;
- page 3 : ajout hypothèses, formule d'économie et remarques ;
- 2026-01 supprimé du tableau mensuel du rapport uniquement.
