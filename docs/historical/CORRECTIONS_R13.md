# Suivi des corrections R13 — 30 septembre 2026

Ce document suit les 40 points de l'audit R12.1. « Corrigé » décrit le défaut logiciel traité. « Encadré » indique qu'un modèle estimatif ou une donnée métier reste nécessaire. L'interface a été modifiée mais sa recette interactive Windows reste non exécutée.

| Point | Résultat dans R13 |
|---|---|
| P01 | Corrigé : plages de coordonnées persistantes ; suppression sans déplacement des zones survivantes. |
| P02 | Corrigé : signature de géométrie par module ; modification réelle détache les strings et leurs MPPT. |
| P03 | Corrigé : numérotation stable ; renumérotation explicite ; identifiant indépendant par module. |
| P04 | Corrigé : nettoyage des coordonnées supprimées et affectations dans l'état avant collecte du projet. |
| P05 | Corrigé : prévalidation et restauration de l'état antérieur si l'import échoue. |
| P06 | Corrigé : écriture temporaire puis remplacement atomique ; images nommées par contenu ; copies précédentes. |
| P07 | Corrigé : contrôle des changements avant fermeture/import ; autosauvegarde vers récupération séparée. |
| P08 | Ajouté : historique de 25 états, Annuler/Rétablir et raccourcis. Les manipulations de dessin sont regroupées avec un délai de 300 ms. |
| P09 | Corrigé : suppression des anciennes caractéristiques électriques lorsque la fiche n'en contient plus. |
| P10 | Corrigé : liens explicites aux lignes de matériel ; migration automatique seulement si marque/modèle correspondent à une ligne unique. |
| P11 | Corrigé : aucune substitution automatique du modèle d'onduleur manquant par un Deye. Les anciennes valeurs utilisateur restent des entrées à vérifier. |
| P12 | Corrigé : vérifications par module/string/onduleur, courant MPPT total, limite par entrée, Voc froid, Vmp chaud, gain bifacial renseigné et puissance PV. Limites non renseignées signalées. |
| P13 | Corrigé : mêmes valeurs de courant/tension et section par string pour la chute de tension et le schéma détaillé. |
| P14 | Corrigé : signatures intégrant échelle, géométrie, chemins, paramètres de parcours et overrides. |
| P15 | Corrigé : vérification de localisation/orientation/période météo ; plusieurs profils possibles. |
| P16 | Corrigé : chaque module doit être raccordé une seule fois ; écrêtage séparé pour chaque onduleur. |
| P17 | Corrigé : puissance active explicite, ou kVA × facteur de puissance ; aucune valeur arbitraire de 125 kW. |
| P18 | Corrigé pour CSV à timestamps avec décalage UTC, y compris vues de 23/25 heures. Excel historique reste à 24 cases/jour et son approximation DST est annoncée. Fuseau configurable. |
| P19 | Corrigé : rejet, zéro ou moyenne des jours précédents ; l'imputation n'utilise plus ses propres valeurs déjà imputées. Méthode conservée dans les métadonnées. |
| P20 | Corrigé : résultats et provenance de simulation enregistrés ; résultats périmés bloqués pour graphique/export ; ancien état d'un autre projet effacé. |
| P21 | Corrigé pour énergie, météo, simulation d'ombre et rapport : worker, progression et annulation ; accès Tk exclusivement depuis son fil principal. |
| P22 | Encadré : obstacles multiples, recouvrements sans double comptage, opacités et mode bypass conservateur. Le couplage électrique I–V complet des strings reste hors de ce modèle. |
| P23 | Corrigé : variation de stockage conservée dans le bilan ; énergie initiale non créditée comme production PV ; énergie terminale non valorisée comme déjà utilisée. |
| P24 | Enrichi : auxiliaires et dégradation de capacité ; maintenance, actualisation, VAN, remplacement paramétré. L'économie reste une projection à tarifs constants, sans fiscalité ni arbitrage horaire. |
| P25 | Enrichi : hauteur de borne par onduleur et réserve par string. Les longueurs sans chemin relevé restent des estimations clairement identifiées. |
| P26 | Enrichi : section choisie, chute de tension, intensité admissible corrigée et calibre renseignés. Le logiciel ne déduit pas l'ampacité ni toutes les conditions de protection d'une installation inconnue. |
| P27 | Enrichi : inventaire supplémentaire AC/inter-modules/terre et quantités, kg/m par section ou string. La masse totale porte sur l'inventaire déclaré, sans supposer les câbles absents. |
| P28 | Corrigé : affichage et réemploi des routes soumis à leur signature et aux paramètres de dimensionnement actuels. |
| P29 | Corrigé : suppression de strings efface MPPT et overrides ; nettoyage des affectations orphelines. |
| P30 | Corrigé : comptage des panneaux réellement placés dans une zone. |
| P31 | Corrigé : snapshot complet des overrides et paramètres ; masses et contrôles du câblage dans le PDF et son JSON. |
| P32 | Corrigé : noms d'exports dépendant du projet, titre R13 et aide actualisée. Les fixtures historiques restent nommées comme leurs sources. |
| P33 | Corrigé : rendu du plan entier à la résolution cible ; aucun PostScript/Ghostscript ni agrandissement du seul viewport. |
| P34 | Ajouté : espacements, retraits et exclusions, conservés dans le projet et appliqués au placement. |
| P35 | Corrigé : polygones dégénérés, auto-intersectés ou contenant des coordonnées non finies refusés. |
| P36 | Corrigé : identifiant de zone et plages extensibles au-delà de 100 lignes, sans superposition des plages. |
| P37 | Réduit : séparation stockage/validation, entrées électriques, checks, jobs et moteurs de calcul ; correspondance logique des onglets. Assemblage historique des mixins conservé pour limiter les régressions. |
| P38 | Corrigé : schéma versionné, prévalidation typée, migration et rejet des versions futures. |
| P39 | Partiel : tests renforcés et versions de dépendances testées consignées. Recette graphique et Windows encore à exécuter. |
| P40 | Partiel : labels non masqués, toolbar adaptable, réglages défilants, dialogue non recentré à chaque événement Map. Le comportement complet sur petits écrans reste à confirmer avec la recette graphique. |

## Données et vérification

Les trois projets joints sont validés sans renumérotation ni altération des strings. Les fichiers 562 et 462 ne fournissent pas les hauteurs nécessaires aux parcours ; les trois ne fournissent pas toutes les masses linéiques. La version signale ces absences et propose les champs de saisie correspondants.

La palette BESS est commune aux vues jour, mois, comparaison embarquée et rapport : jaune, vert, bleu, cyan, rouge et violet. Les scénarios comparés utilisent bleu, orange et vert.

66 tests réussis : stockage interrompu, images immuables et backups, migrations des trois projets, zones conservées, géométrie modifiée, plages >100 lignes, exclusions, puissance et connexions, météo périmée, DST, auxiliaires, SOC initial, signatures, ombres superposées, masses, ampacité, annulation et export complet.

L'import de `app` et la compilation sont vérifiés. Un rapport sur données synthétiques, ainsi que ses graphiques, a été généré ; ce fichier de recette ne constitue pas une étude des projets fournis. Aucun serveur d'affichage Tkinter n'est disponible : ne pas considérer la recette interactive Windows comme validée.
