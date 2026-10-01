# Revue de la base de code — R11

## Travaux réalisés

Le projet reste une application Tkinter. Les calculs géométriques et graphiques nouveaux sont isolés dans `geometry_layout.py` et `energy_charts.py`. L'export est dans `engineering_report.py`. Trois mixins ciblés prennent en charge la géométrie d'installation, les gestes d'édition et la configuration/comparaison. Le modèle énergétique existant et ses équations restent identifiables.

Les 33 tests couvrent les régressions existantes, les panneaux tournés à plusieurs angles, leur aire et leurs limites, l'absence de recouvrement, les hauteurs manquantes/contradictoires, les petits et grands franchissements, les franchissements répartis sur plusieurs segments, la projection de deux terminaux sur un chemin commun et la durée requise pour calculer un retour annuel. Import et compilation de l'application réussis.

R11 ajoute `bess_charts.py`, `diagram_layout.py`, `toolbar_icons.py`, `report_plans.py` et le mixin `diagram_editor.py`. Les tests couvrent aussi les gestes avec zoom/défilement, les blocs électriques sans recouvrement, les bilans horaires, les limites d’axes des graphiques, les cotations et la couverture de l’atlas vectoriel. Un rapport synthétique de 20 pages et ses graphiques ont été inspectés ; les pages de détail contiennent du texte vectoriel et aucune image raster.

## Points à perfectionner, par priorité

| Priorité | Constat actuel | Travail recommandé |
|---|---|---|
| 1 | Pas de recette graphique réalisable dans cet environnement | Exécuter `tools/test_r11_gui.py` sous Windows puis vérifier les gestes, toutes les tailles de fenêtre et un projet réel ; conserver captures et erreurs éventuelles. |
| 1 | Les coordonnées de panneaux encodent encore la zone par pas de 100 lignes | Migrer vers des identifiants stables de zone/panneau, distincts des indices de grille. R10 refuse explicitement plus de 100 lignes par zone au lieu de produire des identifiants ambigus. |
| 1 | Modifier une zone modifie la géométrie des cellules, alors que les affectations peuvent rester enregistrées | Ajouter transactions d'édition et annuler/rétablir ; faire confirmer la réaffectation des strings après régénération. R10 bloque le calcul énergétique des layouts hors zone ou superposés. |
| 1 | Le routage reste une estimation géométrique, avec repli direct | Modéliser les supports, pénétrations, descentes et ponts réellement disponibles. Valider les réserves et le seuil de franchissement sur site. Ajouter l'altitude propre de chaque borne d'onduleur ; R10 utilise une altitude commune réglable. |
| 1 | Les polygones peuvent être redessinés librement | Ajouter validation stricte des polygones simples, interdiction des auto-intersections et contrôles des obstacles traversés. |
| 1 | Les fiches matériel et les copies affectées aux onduleurs coexistent | Introduire un catalogue avec références uniques, révisions et unités ; distinguer valeurs constructeur vérifiées et hypothèses. Les copies placées ne suivent pas automatiquement les modifications des fiches. |
| 1 | Les contrôles électriques sont partiels | Vérifier Voc à froid, domaine MPPT, courant de court-circuit, ampacité, protections et raccordement à partir de fiches vérifiées. Les paramètres/protections manquants ne valent pas conformité. |
| 2 | De nombreux mixins partagent un état mutable et des méthodes redéfinies | Séparer état de projet typé, services de calcul et vues Tkinter ; limiter la profondeur d'héritage. Les modules ajoutés constituent une séparation locale, pas une réécriture complète. |
| 2 | Les onglets sont encore repérés par indices numériques | Remplacer ces indices par un registre de pages nommées ; tester navigation et chargement indépendamment de leur ordre. |
| 2 | Les calculs annuels s'exécutent dans le fil graphique | Passer à une tâche de calcul annulable avec état figé des entrées et remontée de progression ; éviter de modifier le projet pendant un calcul. |
| 2 | L'ombre est géométrique ; les profils utilisent 24 cases par jour | Ajouter modèle électrique de mismatch/bypass et traitement explicite des journées de changement d'heure. Distinguer climat, météo réelle et ciel clair. |
| 2 | Le BESS ne charge qu'au surplus PV et ne revient pas nécessairement au SOC initial | Pour les études financières, traiter le SOC terminal et ajouter vieillissement, rendement variable, indisponibilité et dégradation. Un modèle d'arbitrage nécessite tarifs horaires et stratégie distincte. |
| 2 | Le rapport mentionne les résultats d'ombre historiques sans signature de calcul dédiée | Ajouter signature de provenance à chaque simulation d'ombre et reconstruire un dossier de résultats actuels complet. |
| 2 | Export JPG historique basé sur PostScript/Pillow | Remplacer par un rendu indépendant du canvas, incluant tout le plan, sans dépendance implicite à Ghostscript ni au cadrage de la fenêtre. |
| 3 | Packaging et dépendances non verrouillés | Verrouiller les versions testées, construire sur Windows en intégration continue et vérifier les polices, Tkinter et Matplotlib dans l'exécutable. `main.spec` est conservé mais aucun exécutable n'a été reconstruit ici. |

## Nettoyage

Retirés de la livraison : anciens lanceurs doublons, anciennes listes et notes de version remplacées, anciennes notes PDF/LaTeX devenues incohérentes avec R10, anciens scripts de recette graphique remplacés par celui de R11, caches Python et fichiers de travail. Les projets et plans fournis, les tests de calcul et les modules de calcul/export encore utilisés sont conservés.

La source LaTeX du rapport est produite en parallèle du PDF, avec formules éditables. Son exécution via LuaLaTeX reste à tester dans l'environnement de l'utilisateur. Aucun rapport de site réel ni résultat de conformité n'a été inventé pour cette livraison.
