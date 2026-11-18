# Écomobilité Isère — AlpineQuest

## Couverture départementale

Les fichiers couvrent les arrêts publiés des lignes desservant l’Isère : Cars Région Isère, M réso (SEM, GSV, TPV), L’va et Ruban lorsque leur GTFS est accessible. La disponibilité de chaque source est affichée ; les réseaux indisponibles ne sont pas considérés comme recensés. La couverture est départementale mais ne garantit pas l’exhaustivité des services absents des données ouvertes.

Chaque KMZ conserve **Tous les arrêts ≥ 600 m**, la sélection initiale de montagne, et ajoute **Tous les arrêts en Isère**, à toute altitude, plus **Par ligne** avec les arrêts complets des lignes desservant le département. Le second KMZ regroupe Cars Région et les réseaux locaux L’va/Ruban ; le nom du réseau reste indiqué. Les arrêts extérieurs restent dans les dossiers par ligne pour préparer un trajet traversant une frontière départementale.

Le filtre départemental utilise les contours communaux de l’[API géographique officielle](https://geo.api.gouv.fr/departements/38/communes?format=geojson&geometry=contour), pas un simple rectangle ou le nom de l’arrêt. Les quais sont regroupés selon les stations parentes du GTFS ; un même lieu desservi par plusieurs réseaux peut conserver plusieurs références. Les altitudes des nouveaux arrêts ne sont pas connues et ne sont pas déduites.

Après réimportation, choisir **Parcourir** et n’afficher qu’un dossier utile : vue montagne, département ou ligne. Les liens historiques des 912 points restent opérationnels. Le catalogue web permet de rechercher les stations de tout le département et chaque fiche liste les accès Camptocamp associés dans un rayon de 1 km à vol d’oiseau.


Deux couches de repères avec un lien permanent par arrêt vers une fiche web actualisée à partir des données officielles des réseaux.

**Site et téléchargements : https://jfmouret.github.io/ecomobilite-isere/**

## Première activation de GitHub Pages

Dans ce dépôt, **Settings → Pages → Build and deployment → Source → GitHub Actions**. Ensuite ouvrir **Actions → Actualiser les arrêts et publier → Run workflow** si le premier lancement a échoué pendant la configuration de Pages.

## Vue randonnée légère (conseillée)

Télécharger **Isere_arrets_randonnee.kmz** depuis le site. Il contient seulement les arrêts d’Isère ayant au moins un accès Camptocamp associé à une activité pédestre, raquettes ou ski à 1000 m maximum à vol d’oiseau. Il ne contient aucun dossier caché avec les milliers d’autres arrêts : un affichage global reste limité à cette sélection. Plusieurs références de réseau ou quais peuvent correspondre à un même lieu.

1. Masquer les anciens imports départementaux et importer ce KMZ léger.
2. Toucher un arrêt, puis son lien pour voir les randonnées Camptocamp et les lignes.
3. Sur sa fiche, choisir **Afficher tous les arrêts de cette ligne dans AlpineQuest — télécharger le KMZ** pour la ligne utile.
4. Ouvrir le téléchargement avec AlpineQuest, et masquer la vue randonnée si nécessaire : tous les arrêts de cette ligne, y compris en plaine ou hors Isère, sont alors consultables. Chaque point renvoie à sa fiche et aux horaires.
5. Masquer la ligne importée pour revenir à la sélection randonnée.

La présence d’un accès est une association géographique et contributive, pas une garantie de cheminement piéton, de praticabilité saisonnière ou de desserte à une date donnée. Les branches figurent dans la ligne complète ; lire les horaires pour choisir une course. Les KMZ sont des instantanés et doivent être téléchargés à nouveau pour actualiser leurs points ; les fiches web restent mises à jour automatiquement.

Les fichiers de ligne sont générés quotidiennement et téléchargés uniquement à la demande ; leurs noms stables sont calculés à partir des identifiants officiels. Aucun fichier supplémentaire n’est nécessaire tant qu’une ligne n’est pas choisie.

## Sur Android

1. Ouvrir le site et télécharger `Mreso_600m_en_ligne.kmz` et/ou `Cars_Isere_600m_en_ligne.kmz`.
2. Ouvrir le fichier téléchargé avec AlpineQuest et importer les repères.
3. Toucher un arrêt, afficher sa description et toucher **Consulter les lignes et horaires actualisés**.
4. Sur sa fiche, choisir une ligne puis **Horaires officiels**. Choisir la date, le sens et l’arrêt dans le service officiel.

Masquer ou retirer l’ancien import correspondant pour éviter les points en double. Les nouveaux KMZ conservent les positions et les noms d’origine. Leur contenu est statique mais les liens ouvrent des fiches mises à jour : il n’est pas nécessaire de réimporter les KMZ chaque jour. Les dossiers par ligne reflètent la desserte publiée à la génération du KMZ. Télécharger et réimporter pour actualiser ces dossiers après un changement de desserte. La consultation des fiches et horaires nécessite une connexion ; elle n’est pas un paquet hors ligne.

## Périmètre

- Les 165 points de `Mreso_600m.kmz` et 747 points de `Cars_Isere_600m.kmz` fournis pour ce projet, soit 912 points.
- Altitudes indiquées IGN dans les fichiers initiaux, toutes supérieures ou égales à 600 m ; elles ne sont pas recalculées ni certifiées ici.
- Sélection non exhaustive. Quelques arrêts du réseau régional se situent dans des départements voisins ; ils sont conservés.
- Aucune ancienne liste de lignes n’est utilisée comme une information actuelle.

## Fiabilité des correspondances

Le programme lit les GTFS officiels ISERE, SEM, GSV et TPV, ainsi que LVA et RUBAN lorsqu’ils sont disponibles. Pour L’va et Ruban, le bouton mène au catalogue officiel des horaires pour rechercher la ligne : aucun lien profond saisonnier n’est deviné. Il reconstitue les lignes desservant chaque point via `stop_times → trips → routes`. Une station parente regroupe ses quais ; un quai conserve uniquement ses propres dessertes. L’identification exige le même nom normalisé et une position identique à moins de 0,2 m, ou à défaut un écart maximal de 25 m sans ambiguïté. Une ambiguïté ou disparition produit une mention explicite sans inventer de lignes.

Les lignes décrivent l’offre publiée sur la période du GTFS, pas les services garantis aujourd’hui. Les exceptions calendaires, jours scolaires, réservation, sens, perturbations et prochains départs doivent être consultés auprès du réseau. Les fiches ne présentent aucune donnée comme du temps réel. Les périodes expirées ou futures sont signalées.

Les liens horaires M réso sont extraits du catalogue officiel, ou emploient un code public et une disponibilité horaire confirmés par l’API M. Les liens Région utilisent l’identifiant officiel de chaque ligne dans le calculateur régional. Aucun nom de PDF n’est deviné. L’ouverture manuelle d’un échantillon est nécessaire après une refonte des sites opérateurs ; un code HTTP 200 ne certifie pas à lui seul le bon contenu d’une application web.

## Actualisation et stockage

GitHub Actions lance la récupération chaque jour **à 07 h 15, heure de Paris** (un retard de GitHub est possible), sur modification des sources du projet, ou manuellement avec **Run workflow**. Aucun compte voyageur ni clé API n’est requis. En cas d’échec de téléchargement ou de GTFS invalide, la publication est interrompue et le site précédent reste en place avec sa date de récupération. Vérifier cette date avant le trajet.

Les GTFS sont téléchargés seulement pendant la construction, sans être ajoutés à l’historique Git. Seul le site généré est transmis à Pages, avec un artefact temporaire d’un jour. Le site généré reste constitué de petites pages HTML, données JSON et deux KMZ compressés ; il ne contient aucun GTFS ni image de topo. Sa taille dépend des arrêts et associations présents. Aucun historique quotidien des horaires n’est conservé.

## Sources et licence

- Région Auvergne-Rhône-Alpes / Oùra : [GTFS Cars Région Isère](https://www.data.gouv.fr/api/1/datasets/r/40ee9d6c-3bb9-409e-b670-986212de63f2).
- SMMAG / Mobilités M : [SEM](https://data.mobilites-m.fr/api/gtfs/SEM), [GSV](https://data.mobilites-m.fr/api/gtfs/GSV), [TPV](https://data.mobilites-m.fr/api/gtfs/TPV).
- [Catalogue des horaires M réso](https://www.reso-m.fr/61-lignes-et-horaires.htm) et [métadonnées des lignes](https://data.mobilites-m.fr/api/routers/default/index/routes).

Les données de transports de `arrets.json` et le rapport `correspondances.csv` sont proposés sous [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), avec attribution aux producteurs. Les points sélectionnés, altitudes et icônes proviennent des deux KMZ fournis par l’utilisateur. Cette présentation CAF est indépendante des réseaux. Les fiches officielles et PDF externes restent sur les sites de leurs éditeurs et ne sont pas recopiés.

## Vérification locale

Python 3.12 ou supérieur, sans bibliothèque supplémentaire :

```sh
python -m unittest discover -s tests -v
python build.py
python verify.py
python -m http.server 8000 --directory dist
```

Les fichiers produits sont dans `dist/`. `--cache-only` sert uniquement aux tests locaux avec des téléchargements déjà présents ; il ne faut pas l’utiliser pour une publication actualisée. `arrets.json` inclut les identifiants de correspondance, les périodes des GTFS et leurs empreintes SHA-256. Le rapport CSV permet le contrôle manuel.

## Afficher les arrêts d’une ligne

Chaque KMZ contient **Tous les arrêts** (vue générale) et **Par ligne** (un dossier par ligne). La vue générale conserve les icônes d’origine ; les dossiers par ligne utilisent des pastilles colorées et des noms préfixés par le numéro de ligne. Une palette de 12 couleurs est réutilisée : la couleur seule ne permet pas d’identifier une ligne parmi toutes les autres.

1. Repérer un arrêt dans la vue générale. Sa description contient les numéros connus à la génération ; sa fiche en ligne donne les informations actualisées.
2. Dans **Repères → Explorer les repères**, ouvrir le fichier importé puis **Tous les arrêts** et retirer ces repères de l’affichage avec la commande de masquage du menu.
3. Revenir au fichier, ouvrir **Par ligne**, puis le dossier **Ligne …** souhaité. Dans le menu du dossier, choisir **Tout afficher**.
4. Pour changer de ligne, masquer les repères du dossier précédent puis afficher ceux du suivant.

Après l’import, privilégier **Parcourir** plutôt que **Afficher** tout le fichier. Les dossiers par ligne sont marqués masqués dans le KML ; la façon dont cette préférence est reprise dépend de l’importeur et doit être vérifiée dans AlpineQuest sur le téléphone. Un affichage global peut superposer les copies d’un même arrêt desservi par plusieurs lignes.

La vue générale conserve les 912 points initiaux à partir de 600 m. **Les dossiers par ligne contiennent toutes les stations parentes desservies dans le GTFS**, y compris dans la vallée, et les différentes branches publiées. Les quais sont regroupés par station ; une course peut ne desservir qu’une branche. Les positions et altitudes de la sélection ne sont pas utilisées pour inventer les altitudes des nouvelles stations, qui restent non renseignées. Aucun tracé d’itinéraire n’est dessiné. Le classement par ligne est figé dans le fichier importé, tandis que les fiches liées sont actualisées quotidiennement. Aucune réimportation quotidienne n’est nécessaire pour consulter les fiches à jour.

## Accès et itinéraires Camptocamp depuis l’arrêt choisi

La fiche de chaque arrêt liste les **points d’accès Camptocamp à 1 km maximum à vol d’oiseau**, puis directement les liens vers leurs itinéraires associés. L’activité pédestre est regroupée sous été, raquettes et ski sous hiver ; les activités restent indiquées précisément. Ce regroupement ne valide ni la saison ni les conditions de pratique.

Source : API publique `https://api.camptocamp.org`, documents de type `waypoint_type=access`, leurs associations explicites `all_routes` et les activités `hiking`, `snowshoeing`, `skitouring`. Aucun sommet ou centre de tracé n’est utilisé comme départ. Un accès associé peut servir de départ ou d’arrivée d’une traversée : le topo reste nécessaire. Les liens mènent aux fiches Camptocamp, avec leur module transports / Itinévert lorsqu’il est disponible ; aucun calculateur Navitia n’est hébergé ici.

Le catalogue est paginé dans l’emprise des arrêts des lignes retenues, avec une marge de recherche, puis filtré par distance sphérique non arrondie ≤ 1000 m. Les coordonnées ponctuelles EPSG:3857 sont converties en WGS84. Les détails sont récupérés seulement pour les accès proches, avec trois appels simultanés au maximum et un cache de 24 heures. Le cache est réutilisé par Actions pour limiter les sollicitations ; les GTFS continuent à être récupérés à chaque génération.

Les fiches web restent actualisées automatiquement. Les dossiers supplémentaires été/hiver et les liens contenus dans les KMZ correspondent à leur génération : réimporter pour actualiser ces éléments hors ligne. Le rapprochement ne calcule pas un itinéraire à pied et ne garantit ni chemin, ni franchissement, ni accès hivernal. La couverture dépend des contributions et associations de Camptocamp et des lignes déjà retenues dans le projet.

**Licences distinctes** : transports sous ODbL 1.0 ; noms, positions, activités et associations Camptocamp sous **CC BY-SA 3.0**, avec attribution à Camptocamp.org et ses contributeurs, liens vers les documents et historiques des auteurs, et indication des transformations effectuées. La licence indiquée par l’API est vérifiée ; une licence différente interrompt la génération pour contrôle. Aucune photo, description complète ou trace GPX n’est recopiée. `camptocamp.json` publie séparément les éléments Camptocamp et les rapprochements, avec leur licence et leur provenance. `arrets.json` indique les deux licences et les sources de ses différentes parties.

Les incohérences constatées dans l’ancien catalogue Grenoble-Montagne ne sont pas reprises. Cette intégration utilise les points explicitement classés comme accès dans Camptocamp, sans les présenter comme des accès vérifiés sur le terrain.

### Sources locales additionnelles

- L’va, Vienne Condrieu Agglomération : [GTFS officiel](https://www.data.gouv.fr/api/1/datasets/r/e0831d78-5577-4cae-aa00-de5eeaf3ecb6), ODbL ; [horaires officiels](https://www.lva-mobilite.fr/se-deplacer/plan-et-fiches-horaires-du-reseau).
- Ruban, CAPI : [GTFS officiel](https://www.data.gouv.fr/api/1/datasets/r/34d2cc17-3eb5-4581-917b-a8c06a112e61), ODbL ; [horaires officiels](https://www.rubantransport.com/lignes-regulieres/).

Si un de ces deux flux additionnels échoue, la publication continue avec une mention explicite et sans points supposés pour ce réseau. Un échec d’un des quatre flux initiaux interrompt la publication pour conserver le site précédent daté. Lors de l’extension, le lien GTFS Ruban renvoyait HTTP 403 ; il n’a pas été remplacé par une archive périmée présentée comme actuelle.

## Visorando

Une intégration automatique n’est pas activée. Les [conditions publiées](https://www.visorando.com/mentions-legales.html), section VII, limitent la réutilisation des informations à l’usage privé et interdisent leur rediffusion. Aucune API publique assortie d’une licence ouverte permettant notre réutilisation n’a été identifiée lors de la vérification. L’ajout de leur catalogue nécessiterait un accord ou une voie de réutilisation explicitement autorisée ; aucune collecte de leurs topos n’est effectuée.
