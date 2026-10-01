# Suivi de la todo liste — R11

| Demande | Réalisation | Vérification |
|---|---|---|
| Graphiques jour et mois BESS | Flux séparés, SOC indépendant, scénarios, navigation et valeurs au clic | Bilans, bornes SOC et axes testés ; rendus inspectés |
| Supprimer More et ses champs | Menu de débordement supprimé ; aucun champ dupliqué ; barre sur plusieurs lignes | Recherche des anciens points d’entrée ; recette graphique fournie |
| Icônes professionnelles | Icônes originales dessinées en traits, infobulles et focus clavier | Planche d’icônes inspectée |
| Tutoriel à jour | Guide avec les mêmes icônes et commandes que les barres | Guide construit depuis le catalogue des outils |
| Cotations noires Times New Roman | Doubles flèches continues, écarts et prévisualisation inclus | Tests du rendu des trois axes de cotation |
| Drag et espacement Electrical | Gauche : vue ; droite : sélection ; groupe sélectionné déplaçable ; réagencement selon tailles | Gestionnaires testés avec zoom/défilement et grands blocs |
| Rapport PDF lisible | Layout, strings, chemins A/B vectoriels ; atlas numéroté ; PDF/SVG associés | Rapport synthétique 540 panneaux, 20 pages ; texte vectoriel confirmé |

## Validation

33 tests passent. Import et compilation Python vérifiés. Pas d’affichage Tkinter disponible : le script `tools/test_r11_gui.py` est fourni pour la recette Windows, mais n’a pas été exécuté ici. Aucun exécutable Windows reconstruit. La source LaTeX reste fournie ; sa compilation n’a pas été exécutée.

## Historique R10



| Demande | État dans le code |
|---|---|
| Espacement et sélection multiple du schéma | Implémentés ; gestes et liste Shift/Ctrl, déplacement groupé |
| Retrait Site wiring / Electrical data | Retirés de la barre du schéma |
| Guide Home développé | Dix rubriques détaillées adaptées du tutoriel fourni |
| Transformation des zones à la souris | Priorité rétablie face au déplacement de vue ; sommets de polygones transformables |
| Hauteurs par polygone | Saisie et persistance ; indépendantes de Shadow |
| Rotation des panneaux | Grille rigide, filtrage aux limites, suppression des chevauchements interzones à la génération |
| Câblage 3D et zones proches | Hauteurs traversées, seuil de pont réglable, réserves et légende explicites |
| Refonte BESS | Comparaison intégrée, graphiques cohérents, calcul unique ; résultats périmés masqués |
| Rapport PDF depuis Home | PDF, LaTeX à équations éditables, figures, entrées JSON ; mise en page sobre |
| Configuration matériel depuis Home | Déplacée ; Variable explorer agrandi |
| Cotations CAO | Modes aligné/horizontal/vertical, lignes d'attache, doubles flèches, positionnement du texte |
| Revue architecture | Audit et priorités dans AUDIT_TECHNIQUE_FR.md |
| Nettoyage | Sources utiles, tests actuels et projets conservés ; doublons/caches/documents obsolètes retirés |

## Validation et limites

25 tests automatisés passent ; import de l'application et compilation réussis. Rapport de contrôle sur données synthétiques généré et vérifié visuellement. Pas d'affichage Tkinter disponible : recette graphique Windows non exécutée, script fourni. Compilation LuaLaTeX non exécutée ; le PDF est généré sans LaTeX. Se reporter à l'audit pour les limites du modèle et les travaux restant recommandés.

## Décisions explicites

- Aucun seuil de franchissement réel supposé : 0 m initialement, à régler.
- Aucune hauteur Shadow substituée à une hauteur Installation manquante.
- Résultats énergétiques historiques invalidés après changement des entrées.
- Aucun calcul de retour annuel pour un profil inférieur à une année complète.
- Aucun projet de démonstration pris pour une étude réelle.


## R12 — 30 septembre 2026

Interface : icônes 12 px + labels ; correction du gestionnaire global Map qui recentrait les infobulles ; aide des outils intégrée au How it works.
Calcul : module string_sizing indépendant de Tk pour les sections DC par string et masses avec poids linéiques constructeur ; signature des entrées, inconnues explicites et export CSV enrichi. Nouveaux paramètres JSON cable_string_params et cable_mass_by_section. Variable TOTAL_CABLE_WEIGHT_KG / alias POIDS_TOTAL_CABLAGES_KG.
Géométrie : rotation ciblée d’une zone avec recalcul transactionnel, conservation des autres zones et invalidation des raccordements affectés.
Validation : 43 tests unitaires/régression réussis, import app réussi. Recette GUI enrichie (labels, infobulle, nouveaux champs JSON), mais non exécutée dans cette session : aucun affichage X disponible ; téléchargement d’un affichage virtuel refusé par le contrôle automatique d’autorisation.


## R12.1 — 30 septembre 2026

Demande utilisateur : retirer les textes au survol des boutons et la rotation ajoutée en R12 ; établir la liste des problèmes sans les corriger.
Retraits : classe Tooltip et toutes ses liaisons retirées ; bouton, module et héritage ZoneRotationMixin supprimés ; les trois tests de cette fonction retirée sont supprimés. Les labels à côté des icônes et le guide How it works restent.
Validation : 40 tests réussis, import app réussi ; recette GUI ajustée mais non exécutée faute d’affichage. Audit read-only exécuté sur états synthétiques et projets joints.
Livrables : AUDIT_R12_1.md, audit_findings.json (40 constats identifiés et classés), audit_probes.json et tools/audit_r12_1.py. Aucun des 40 problèmes n’a été corrigé dans cette version ; ils sont soumis au choix utilisateur.


## R13 — 30 septembre 2026

Demande : corriger/nettoyer l’ensemble des points de l’audit et rendre les graphiques BESS plus vifs, sans réintroduire les infobulles ni le nouveau bouton de rotation.
Stockage versionné et atomique, récupération séparée, rollback, historique ; identifiants et plages de zones stables ; calculs par string/onduleur, ampacité et inventaire déclarés ; provenance météo/énergie/ombre ; tâches en arrière-plan ; modèle d’ombre étendu, DST explicite CSV, auxiliaires/dégradation et économie actualisée ; export plan complet ; palette commune vive.
Vérification : 66 tests réussis ; trois projets JSON inchangés après migration/round-trip ; comptages de zones exacts et géométrie contrôlée ; application importable, compilation vérifiée ; rapport et graphiques synthétiques générés. Recette Tk/Windows non exécutée : aucun DISPLAY. Voir CORRECTIONS_R13.md pour les limites de modèle et les points restant à confirmer visuellement.
