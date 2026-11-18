# Vérification des traces de randonnée hivernale IGN/Petzl

Vérification effectuée le 18 novembre 2026. Si la couche appelée « Traces hiver » dans AlpineQuest est bien celle-ci, les éléments suivants s’appliquent. Pour une autre source, son fichier AQX ou son URL devra être examiné séparément.

- Identifiant WMTS : `TRACES.RANDO.HIVERNALE`, titre « Traces de randonnée hivernale ».
- Édition annoncée : 2025-12-10.
- Catalogue officiel : https://cartes.gouv.fr/rechercher-une-donnee/dataset/PETZL_TRACES-RANDO-HIVERNALE
- Présentation IGN : https://www.ign.fr/actualites/traces-de-randonnee-hivernale-les-alpes-desormais-entierement-couvertes-dans-lappli-cartes-ign
- Capacités WFS : https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities
- Type WFS : `TRACES.RANDO.HIVERNALE:traces_rando_hivernale`.

La requête DescribeFeatureType a retourné les champs `cleabs` (texte), `nom_de_la_trace` (texte), `passage_delicat` (booléen), `the_geom` (géométrie). Aucun champ de départ, parking ou point d’accès distinct n’est annoncé.

Une requête GetFeature de deux objets, en GeoJSON et CRS84, a renvoyé des géométries LineString : « Pointe de Calabre depuis Le Fornet » et « Le Merbelay depuis Le Villard ». Il s’agit de coordonnées vectorielles exploitables, et non uniquement de pixels.

La fiche de métadonnées annonce une Licence Ouverte / Open License, compatible ODC-BY / CC-BY 2.0, et renvoie vers Skitourenguru et Yéti pour télécharger les traces GPX. La licence spécifique et les attributions devraient être conservées lors d’une future intégration ; cette recherche n’a pas conduit à republier les géométries.

Conclusion : les traces sont géoréférencées, mais la présence de points de départ explicitement définis n’est pas établie. Le nom « depuis … » ne suffit pas à déterminer la coordonnée de départ d’une géométrie linéaire. Les extrémités peuvent notamment correspondre à des segments et ne sont pas utilisées automatiquement. Le rapprochement bus à 1 km n’est pas activé pour cette couche. Les accès Camptocamp restent la source hivernale opérationnelle du projet.
