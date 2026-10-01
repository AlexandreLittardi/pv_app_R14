# Audit de PV App R12.1 — 30 septembre 2026

Les deux seuls changements fonctionnels de R12.1 sont le retrait des infobulles des boutons et de la commande de rotation ajoutée en R12. Les problèmes ci-dessous n’ont pas été corrigés : ils sont recensés pour décision utilisateur.

Périmètre : code R12.1, tests, trois JSON joints et image fournie. Aucune donnée constructeur extérieure ni étude de site n’a été supposée. La recette visuelle n’a pas été exécutée faute d’affichage. Cet inventaire des défauts identifiés ne garantit pas l’absence d’autres défauts.

## Statuts et priorité

- R : défaut reproduit sur un état synthétique ou les projets joints.
- C : constat confirmé par lecture du code ; geste complet dans l’interface non testé.
- L : limite explicite du modèle ou fonction absente, pas nécessairement un bug.
- V : point à vérifier visuellement ou sur le poste cible.
- Haute : peut modifier les références, les données ou le résultat technique. Moyenne : limite fonctionnelle, ergonomique ou de maintenance. Ce classement n’est pas une décision de correction.

## Inventaire

| ID | Priorité | Statut | Problème |
|---|---|---|---|
| P01 | Haute | R | Suppression de zone : références de panneaux décalées |
| P02 | Haute | R | Régénération : strings conservés sur une géométrie différente |
| P03 | Haute | R | Identifiants modifiés lors du dessin et de la sauvegarde |
| P04 | Haute | R | Nettoyage incomplet avant sauvegarde |
| P05 | Haute | C | Import non transactionnel |
| P06 | Haute | C | Sauvegarde non atomique, sans copie de secours |
| P07 | Haute | C | Pas de protection des modifications non enregistrées |
| P08 | Moyenne | L | Pas d’annuler/rétablir |
| P09 | Haute | R | Anciennes valeurs électriques conservées |
| P10 | Haute | C | Catalogue et onduleurs placés peuvent diverger |
| P11 | Haute | C | Références constructeur imposées par défaut |
| P12 | Haute | L | Contrôles électriques globaux et partiels |
| P13 | Haute | C | Deux calculs DC peuvent donner des résultats différents |
| P14 | Haute | R | Signature du dossier électrique incomplète |
| P15 | Haute | C | Météo importée réutilisable avec une mauvaise orientation |
| P16 | Haute | R | Production indépendante du raccordement réel |
| P17 | Haute | R | Puissance AC supposée et confusion kVA/kW |
| P18 | Moyenne | L | Fuseau fixe et journées de 24 heures |
| P19 | Moyenne | L | Consommations manquantes estimées automatiquement |
| P20 | Haute | C | Résultats d’ombre anciens ou d’un autre projet |
| P21 | Moyenne | C | Calculs et téléchargements bloquent l’interface |
| P22 | Moyenne | L | Ombre géométrique simplifiée |
| P23 | Moyenne | L | Comparaison BESS sensible aux SOC de début/fin |
| P24 | Moyenne | L | BESS et rentabilité restent des modèles simplifiés |
| P25 | Haute | L | Longueurs de câbles encore estimatives |
| P26 | Haute | L | Section proposée : chute de tension seulement |
| P27 | Moyenne | L | Poids du câblage : périmètre incomplet |
| P28 | Moyenne | C | Table Routes susceptible d’afficher des longueurs anciennes |
| P29 | Haute | C | Suppression de string : paramètres liés conservés |
| P30 | Haute | R | Variables de panneaux par zone incorrectes |
| P31 | Moyenne | C | Snapshot du rapport incomplet pour les ajouts R12 |
| P32 | Moyenne | C | Titres et documentation encore spécifiques à un site/version |
| P33 | Moyenne | C | Export JPG dépendant de la vue et de Ghostscript |
| P34 | Moyenne | L | Calepinage sans jeux ni corridors automatiques |
| P35 | Haute | C | Polygones non validés |
| P36 | Moyenne | L | Coordonnées de panneaux limitées à 100 lignes par zone |
| P37 | Moyenne | C | Architecture fragile à modifier |
| P38 | Moyenne | C | Format projet sans schéma de version strict |
| P39 | Moyenne | V | Recette graphique et livrable Windows non validés ici |
| P40 | Moyenne | V | Lisibilité sur petits écrans à vérifier |

## Détails et preuves

### P01 — Suppression de zone : références de panneaux décalées

Supprimer une zone renumérote les row_base des zones suivantes sans migrer panels, strings et affectations. Reproduction : le panneau (0,0) se retrouve sur l’ancienne deuxième zone et (100,0) ne possède plus de rectangle physique.

Source : `mixins/zone_tools.py: delete_active_zone ; mixins/installation_geometry.py: _recalculate_zone_grids`.

### P02 — Régénération : strings conservés sur une géométrie différente

Après déplacement, redimensionnement, angle ou changement de dimensions des modules, les coordonnées de cellules réutilisées conservent leurs anciennes connexions. Reproduction : le centre passe de (50,85) à (350,85), le string reste affecté à (0,0).

Source : `mixins/zone_tools.py: generate_panels_from_zones ; mixins/installation_geometry.py: generate_panels_from_zones ; mixins/stringing_tools.py: update_dimensions`.

### P03 — Identifiants modifiés lors du dessin et de la sauvegarde

Lorsque continuous_panel_numbers est actif, draw_grid et _prepare_project_save renumérotent les panneaux. Un simple enregistrement peut rendre obsolètes des identifiants déjà utilisés sur un plan ou un export. Reproduction : panneau 99 devenu 1.

Source : `mixins/project_integrity.py: draw_grid, _prepare_project_save`.

### P04 — Nettoyage incomplet avant sauvegarde

normalize_project nettoie une copie, mais _prepare_project_save ne reporte pas les strings et affectations nettoyées dans l’état. save_project sérialise ensuite ces champs de l’état initial. Reproduction : une coordonnée orpheline retirée de la copie reste dans self.strings.

Source : `mixins/project_integrity.py: _prepare_project_save ; mixins/project_io.py: save_project`.

### P05 — Import non transactionnel

Le chargement modifie le nom, le chemin actif et de nombreux champs avant d’avoir validé tous les paramètres. Une erreur tardive peut laisser un mélange du projet précédent et du projet importé, avec le nouveau chemin de sauvegarde.

Source : `mixins/project_io.py: _load_project_file`.

### P06 — Sauvegarde non atomique, sans copie de secours

Le JSON existant est ouvert directement en mode w. Une interruption ou erreur pendant json.dump peut laisser un fichier tronqué. L’image est enregistrée séparément ; son échec est seulement imprimé et ne bloque pas la réussite du JSON.

Source : `mixins/project_io.py: save_project`.

### P07 — Pas de protection des modifications non enregistrées

Pas de suivi dirty ni de demande de sauvegarde avant ouverture d’un autre projet ou fermeture de la fenêtre. L’autosauvegarde réécrit le projet actif toutes les cinq minutes ; il n’existe pas d’historique local de sauvegardes.

Source : `main.py ; app.py: __init__ ; mixins/project_io.py: import_project, _auto_save`.

### P08 — Pas d’annuler/rétablir

Aucun historique undo/redo pour panneaux, zones, strings, affectations et suppressions. Une mauvaise manipulation géométrique ne peut pas être annulée depuis l’interface.

Source : `app.py ; mixins/editor_interactions.py ; mixins/zone_tools.py ; mixins/stringing_tools.py`.

### P09 — Anciennes valeurs électriques conservées

Si une fiche module perd Imp, Vmp, Voc ou Isc, _sync_module_power ne retire pas les anciennes valeurs de diagram_electrical_specs. Reproduction : supprimer Vmp de la fiche conserve vmp_v=40 dans le schéma.

Source : `mixins/project_integrity.py: _sync_module_power`.

### P10 — Catalogue et onduleurs placés peuvent diverger

L’onduleur placé contient une copie material_row. Les modifications ultérieures de sa fiche ne mettent pas automatiquement à jour cette copie ; certains calculs utilisent la fiche et d’autres la copie.

Source : `mixins/inverter_tools.py ; mixins/material_tools.py ; self_consumption.py: production_from_program`.

### P11 — Références constructeur imposées par défaut

normalize_project remplace des modèles ee par une référence Deye précise. Le schéma détaillé peut aussi afficher HYBRID_MODEL ou BESS_MODEL en l’absence de référence saisie. Une donnée absente peut ainsi prendre l’apparence d’un modèle choisi.

Source : `project_validation.py: normalize_project ; detailed_electrical.py: HYBRID_MODEL, BESS_MODEL, build_detailed_model`.

### P12 — Contrôles électriques globaux et partiels

Les valeurs de contrôle sont communes à tous les modules/onduleurs. Voc à froid, Vmp STC et certains courants sont vérifiés, mais Vmp à chaud, gain bifacial, limites propres à chaque entrée, sélectivité et conformité d’installation ne le sont pas complètement. Les configurations multi-modèles sont mal représentées.

Source : `project_validation.py: audit_project ; detailed_electrical.py: build_detailed_model`.

### P13 — Deux calculs DC peuvent donner des résultats différents

Le tableau String sizing tient compte des overrides courant/tension par string ; le schéma électrique détaillé utilise son propre couple Imp/Vmp et une section saisie séparément dans electrical_design. Les overrides de R12 n’y sont pas intégrés.

Source : `mixins/string_sizing.py: size_string ; detailed_electrical.py: build_detailed_model`.

### P14 — Signature du dossier électrique incomplète

source_fingerprint omet notamment px_per_mm, dimensions des panneaux, roof_polygons et routing_settings. Reproduction : modifier l’échelle et la réserve laisse la signature inchangée si le plan de routes n’a pas encore été recalculé.

Source : `detailed_electrical.py: source_fingerprint`.

### P15 — Météo importée réutilisable avec une mauvaise orientation

Un profil GTI téléchargé pour une inclinaison/azimut/localisation reste utilisable après modification de ces valeurs. La signature exige un nouveau calcul, mais production_from_program ne vérifie pas que les métadonnées query correspondent aux paramètres courants.

Source : `mixins/self_consumption_ui.py: _download_historical_weather ; self_consumption.py: production_from_program`.

### P16 — Production indépendante du raccordement réel

La production compte tous les panneaux et écrête à la somme des puissances AC, sans production/écrêtage par bloc ni exigence de connexion complète string–MPPT. Reproduction : un panneau sans onduleur placé produit de l’énergie si un bloc existe. Un onduleur sous-chargé peut compenser fictivement un autre surchargé.

Source : `self_consumption.py: production_from_program`.

### P17 — Puissance AC supposée et confusion kVA/kW

En l’absence de Puissance (kVA) sur une copie d’onduleur, le modèle énergétique prend 125. Cette puissance apparente est utilisée comme limite en kW, sans facteur de puissance. La reproduction P16 fonctionne sans aucune fiche d’onduleur placé.

Source : `self_consumption.py: production_from_program`.

### P18 — Fuseau fixe et journées de 24 heures

Le modèle énergétique et l’import météo imposent Europe/Rome. Les journées sont toujours de 24 cases ; une heure manquante est interpolée et une heure doublée moyennée. Ce n’est pas une représentation exacte des changements d’heure ni d’un site dans un autre fuseau.

Source : `self_consumption.py: read_open_meteo_json, timestamps, production_from_program`.

### P19 — Consommations manquantes estimées automatiquement

Les valeurs absentes sont remplies avec la moyenne des mêmes heures des sept jours précédents, y compris des valeurs déjà estimées. Les indices sont signalés, mais il n’existe pas de choix de méthode ni d’évaluation de sensibilité ; les résultats peuvent dépendre de cette hypothèse.

Source : `self_consumption.py: read_daily_excel`.

### P20 — Résultats d’ombre anciens ou d’un autre projet

shadow_simulation_results n’a pas de signature des entrées. Le JSON projet ne l’enregistre pas et _load_project_file ne le remet pas à zéro. Des résultats en mémoire du projet A peuvent rester après ouverture du projet B et être repris par les variables SIM_* ou le snapshot du rapport.

Source : `app.py: shadow_simulation_results ; mixins/project_io.py: save_project, _load_project_file ; mixins/spreadsheet_tools.py: _get_spreadsheet_variables ; engineering_report.py: report_content`.

### P21 — Calculs et téléchargements bloquent l’interface

Les boucles annuelles, les simulations d’ombre et le téléchargement météo fonctionnent dans le fil Tkinter. update_idletasks rafraîchit les tâches de dessin mais ne rend pas ces opérations asynchrones. Pas de tâche annulable ; le téléchargement attend jusqu’à 60 secondes.

Source : `mixins/self_consumption_ui.py: _calculate_self_consumption, _download_historical_weather ; mixins/shadow_simulation.py`.

### P22 — Ombre géométrique simplifiée

L’obstacle modélisé est unique, de forme simplifiée ; la perte de puissance suit la fraction ombragée. Pas de diodes bypass, mismatch électrique, masques multiples arbitraires ou détails d’obstacles relevés sur site.

Source : `mixins/shadow_geometry.py ; mixins/shadow_energy.py ; self_consumption.py: production_from_program`.

### P23 — Comparaison BESS sensible aux SOC de début/fin

Les scénarios démarrent au SOC saisi et ne sont pas contraints à terminer au même SOC. Un SOC initial élevé fournit une énergie initiale dont l’origine n’est pas comptée comme PV produit sur la période. Les bilans indiquent les SOC, mais la valorisation ne corrige pas cette énergie de frontière.

Source : `battery_dispatch.py: simulate_bess ; energy_economics.py: evaluate_options`.

### P24 — BESS et rentabilité restent des modèles simplifiés

Rendement et capacités constants, deux batteries partageant les mêmes limites de puissance, charge au surplus PV seulement. Pas de vieillissement, auxiliaires, indisponibilité, arbitrage horaire, financement, maintenance ni remplacement dans le payback simple. Ce sont des limites déjà documentées, pas des erreurs de bilan.

Source : `battery_dispatch.py ; energy_economics.py`.

### P25 — Longueurs de câbles encore estimatives

Les trajets emploient réseau/polygones puis repli orthogonal direct. Les supports, pénétrations et descentes exactes ne sont pas définis ; hauteur de borne d’onduleur et réserve sont communes. Le repli direct ne prouve pas la faisabilité d’installation.

Source : `mixins/cable_network.py: compute_cable_route ; mixins/two_pole_cables.py: _calculate_two_pole_route ; mixins/installation_geometry.py: _show_installation_heights`.

### P26 — Section proposée : chute de tension seulement

La section standard est déterminée uniquement par la chute de tension à Imp/Vmp. Pas de correction thermique, groupement, courant admissible, court-circuit ou coordination des protections. La section proposée n’est pas automatiquement la section retenue dans le dossier détaillé.

Source : `mixins/notes_tools.py: calculate_dc_cable_size ; mixins/string_sizing.py: size_string`.

### P27 — Poids du câblage : périmètre incomplet

TOTAL_CABLE_WEIGHT_KG porte uniquement sur les conducteurs DC A+B string–onduleur calculés, pas sur les liaisons inter-modules, AC/BESS, chemins ni accessoires. La masse dépend de la section proposée et d’un kg/m unique par section, sans choix de modèle de câble réel. Une entrée manquante rend le total indisponible.

Source : `mixins/string_sizing.py: size_string, _cable_mass_summary`.

### P28 — Table Routes susceptible d’afficher des longueurs anciennes

Le tableau Routes lit cable_network_routes sans vérifier get_two_pole_route à chaque ligne. Le tableau String sizing vérifie la provenance. Après certains changements géométriques/électriques, les deux présentations peuvent diverger jusqu’au recalcul des routes.

Source : `mixins/notes_tools.py: _refresh_cable_route_table ; mixins/string_sizing.py: _refresh_string_sizing_table ; mixins/two_pole_cables.py: get_two_pole_route`.

### P29 — Suppression de string : paramètres liés conservés

delete_active_string et clear_all_strings ne nettoient pas systématiquement string_mppt_assignment et les nouveaux cable_string_params. Réutiliser un nom de string peut réutiliser une ancienne affectation ou d’anciens courant/tension.

Source : `mixins/stringing_tools.py: delete_active_string, clear_all_strings ; mixins/string_sizing.py: _size_string_route`.

### P30 — Variables de panneaux par zone incorrectes

ZONE*_PANEL_COUNT utilise rows×cols, pas le nombre de panneaux effectivement présents. Les trois projets donnent respectivement 558 au lieu de 537, 578 au lieu de 562 et 482 au lieu de 462 dans la somme de ces variables.

Source : `mixins/spreadsheet_tools.py: _get_zone_string_insert_vars ; audit_probes.json: attached_projects`.

### P31 — Snapshot du rapport incomplet pour les ajouts R12

project_inputs.json du rapport n’intègre ni cable_string_params ni cable_mass_by_section ; le PDF n’affiche pas les masses. Les longueurs/sections calculées sont exportées, mais les nouvelles entrées nécessaires pour reproduire le poids ou les overrides manquent.

Source : `engineering_report.py: report_content ; mixins/project_integrity.py: _project_snapshot`.

### P32 — Titres et documentation encore spécifiques à un site/version

Certaines fenêtres conservent Volfrigo 516, le rapport affiche Application R11, et certains textes techniques anciens décrivent une rotation panneau par panneau alors que la grille courante tourne en bloc. Ces intitulés peuvent induire en erreur dans un projet Frimo ou une autre étude.

Source : `mixins/self_consumption_ui.py ; engineering_report.py: report_content ; mixins/ui_builders.py: TECHNICAL_GUIDE`.

### P33 — Export JPG dépendant de la vue et de Ghostscript

L’export utilise le PostScript du canvas sans cadrage explicite de tout le plan puis agrandit le raster. Un plan défilé peut être incomplet ; l’agrandissement ne crée pas de détail supplémentaire et le rendu PostScript dépend de Ghostscript. Le PDF vectoriel est une autre voie existante.

Source : `mixins/project_io.py: export_jpg_final`.

### P34 — Calepinage sans jeux ni corridors automatiques

La grille est bord à bord. Aucun paramètre général d’écart de montage, accès, recul périphérique ou corridor n’est appliqué automatiquement. La géométrie valide ne constitue pas une validation de l’implantation d’installation.

Source : `geometry_layout.py: grid_spec ; mixins/installation_geometry.py: _valid_zone_cell ; user_guide.py`.

### P35 — Polygones non validés

La création accepte un polygone dès trois points, sans refuser l’auto-intersection, les points identiques ou l’aire nulle. L’édition permet aussi de créer ces cas ; les calculs de présence/routage sur un tel polygone peuvent être ambigus.

Source : `mixins/paths_tools.py: _finish_polygon_draw ; mixins/editor_interactions.py: on_left_drag`.

### P36 — Coordonnées de panneaux limitées à 100 lignes par zone

La zone est encodée par index×100. Une zone au-delà de 100 lignes est refusée et les IDs physiques sont couplés à l’ordre des zones. Cette limite structurelle contribue au problème P01.

Source : `mixins/installation_geometry.py: _recalculate_zone_grids`.

### P37 — Architecture fragile à modifier

De nombreux mixins redéfinissent les mêmes méthodes et partagent un état mutable. Les onglets sont identifiés par des indices numériques. Ajouter/réordonner un onglet ou modifier une méthode peut toucher d’autres comportements difficiles à isoler.

Source : `app.py: PVLayoutRibbonApp ; mixins/canvas_grid.py ; mixins/responsive_ui.py`.

### P38 — Format projet sans schéma de version strict

Pas de version de schéma projet ni de validation complète avant application des champs. Des structures, coordonnées, nombres non finis ou types invalides peuvent échouer tardivement. Les migrations actuelles sont des règles implicites dans normalize_project.

Source : `mixins/project_io.py: _load_project_file ; project_validation.py: normalize_project`.

### P39 — Recette graphique et livrable Windows non validés ici

Les 40 tests et l’import Python passent ; ils ne prouvent pas tous les gestes, le rendu haute densité, la mise en page des fenêtres, les exports Ghostscript ou le fonctionnement d’un exécutable Windows. La recette GUI reste non exécutée faute d’affichage. Les dépendances ne sont pas verrouillées à des versions exactes.

Source : `tools/test_r11_gui.py ; requirements.txt ; main.spec`.

### P40 — Lisibilité sur petits écrans à vérifier

Les outils se répartissent sur plusieurs lignes, certains labels longs sont masqués, des panneaux latéraux ont une largeur minimale et les dialogues sont recentrés globalement. Les boutons avec labels peuvent être tronqués et certains formulaires peuvent dépasser la hauteur disponible. Aucun défaut visuel précis n’est affirmé sans recette à l’écran.

Source : `mixins/responsive_ui.py: _layout_responsive, _fit_dialog, _cap_mapped_dialog ; mixins/string_sizing.py: _build_string_sizing_page`.

## Observations sur les fichiers joints

Les trois projets possèdent une image résolue, sans panneau hors zone ou superposé selon les contrôles actuels, sans panneau non affecté à un string et sans doublon d’appartenance. Ces contrôles ne constituent pas une validation électrique complète. Les éléments ci-dessous sont des données manquantes ou des incohérences de métadonnées des fichiers, à distinguer des bugs du logiciel.

| Fichier | Panneaux réellement enregistrés | Somme des variables de zones | Zones sans hauteur de câblage |
|---|---:|---:|---:|
| Usine_Frimo_517.json | 537 | 558 | 0 / 9 |
| Usine_Frimo_562.json | 562 | 578 | 11 / 11 |
| Usine_Frimo_462.json | 462 | 482 | 8 / 8 |

- Le fichier nommé Usine_Frimo_517 contient 537 panneaux ; le nom de fichier ne reflète donc pas son contenu.
- Les trois project_name valent « Projet Importé », ce qui rend les listes de projets moins distinctes. La sauvegarde d’images utilise ce nom ; des projets de même nom dans un même dossier peuvent partager/écraser la même image.
- Les fichiers 562 et 462 ne contiennent pas electrical_checks ; l’audit électrique demande les valeurs manquantes.
- Aucun des trois fichiers ne contient de poids linéiques cable_mass_by_section : le poids nouvellement calculé reste indisponible tant que ces entrées ne sont pas fournies.

## Validation de la livraison

40 tests existants après retrait des trois tests de la fonction de rotation supprimée : réussis. Import app : réussi. Les sondes `tools/audit_r12_1.py` ont été exécutées ; leurs résultats sont dans `audit_probes.json`. Elles sont en lecture seule et utilisent des états synthétiques. Les projets joints restent byte-identiques. La recette GUI est adaptée aux retraits mais n’a pas été exécutée dans cette session.
