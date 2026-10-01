# Conventions de maintenance

Application Python/Tkinter, sans application web.

- Lire CODEMAP.md avant d'explorer ; privilégier les plages de lignes utiles.
- Conserver les projets utilisateur dans pv_projects/ ; ne pas les modifier pour une recette.
- Travailler sur une branche dédiée et par changements ciblés.
- Garder les calculs indépendants de Tkinter lorsque possible.
- Les mixins sont assemblés dans app.py : vérifier l'ordre de résolution des méthodes.
- Les onglets actuels utilisent encore des indices fixes : Home 0, Installation 1, Layout 2, Stringing 3, MPPT 4, Shadow 5, Spreadsheet 6, Diagram 7, Cabling 8, Energy/BESS 9. Ne pas changer leur ordre sans migration des gestionnaires.
- Un nouveau paramètre doit être sauvegardé, rechargé et inclus dans la signature du calcul qu'il affecte.
- Ne pas substituer une donnée manquante par une valeur constructeur supposée ; identifier les hypothèses existantes.
- Éviter les ajouts aux gros modules de canvas et de zone ; utiliser des fonctions dédiées et des points d'intégration ciblés.
- Vérifier l'import de app, exécuter les tests de calcul, puis tools/test_r11_gui.py avec un affichage Tkinter pour toute modification d'interface.
- Régénérer CODEMAP.md avec tools/gen_codemap.py après les modifications.
