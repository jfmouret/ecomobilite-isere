# Écomobilité Isère — AlpineQuest

Deux couches de repères avec un lien permanent par arrêt vers une fiche web actualisée à partir des données officielles des réseaux.

**Site et téléchargements : https://jfmouret.github.io/ecomobilite-isere/**

## Première activation de GitHub Pages

Dans ce dépôt, **Settings → Pages → Build and deployment → Source → GitHub Actions**. Ensuite ouvrir **Actions → Actualiser les arrêts et publier → Run workflow** si le premier lancement a échoué pendant la configuration de Pages.

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

Le programme lit les quatre GTFS officiels ISERE, SEM, GSV et TPV. Il reconstitue les lignes desservant chaque point via `stop_times → trips → routes`. Une station parente regroupe ses quais ; un quai conserve uniquement ses propres dessertes. L’identification exige le même nom normalisé et une position identique à moins de 0,2 m, ou à défaut un écart maximal de 25 m sans ambiguïté. Une ambiguïté ou disparition produit une mention explicite sans inventer de lignes.

Les lignes décrivent l’offre publiée sur la période du GTFS, pas les services garantis aujourd’hui. Les exceptions calendaires, jours scolaires, réservation, sens, perturbations et prochains départs doivent être consultés auprès du réseau. Les fiches ne présentent aucune donnée comme du temps réel. Les périodes expirées ou futures sont signalées.

Les liens horaires M réso sont extraits du catalogue officiel, ou emploient un code public et une disponibilité horaire confirmés par l’API M. Les liens Région utilisent l’identifiant officiel de chaque ligne dans le calculateur régional. Aucun nom de PDF n’est deviné. L’ouverture manuelle d’un échantillon est nécessaire après une refonte des sites opérateurs ; un code HTTP 200 ne certifie pas à lui seul le bon contenu d’une application web.

## Actualisation et stockage

GitHub Actions lance la récupération chaque jour **à 07 h 15, heure de Paris** (un retard de GitHub est possible), sur modification des sources du projet, ou manuellement avec **Run workflow**. Aucun compte voyageur ni clé API n’est requis. En cas d’échec de téléchargement ou de GTFS invalide, la publication est interrompue et le site précédent reste en place avec sa date de récupération. Vérifier cette date avant le trajet.

Les GTFS sont téléchargés seulement pendant la construction, sans être ajoutés à l’historique Git. Seul le site généré est transmis à Pages, avec un artefact temporaire d’un jour. Première génération : environ **3,6 Mo pour le site complet**, dont deux petits KMZ. Aucun historique quotidien des horaires n’est conservé.

## Sources et licence

- Région Auvergne-Rhône-Alpes / Oùra : [GTFS Cars Région Isère](https://www.data.gouv.fr/api/1/datasets/r/40ee9d6c-3bb9-409e-b670-986212de63f2).
- SMMAG / Mobilités M : [SEM](https://data.mobilites-m.fr/api/gtfs/SEM), [GSV](https://data.mobilites-m.fr/api/gtfs/GSV), [TPV](https://data.mobilites-m.fr/api/gtfs/TPV).
- [Catalogue des horaires M réso](https://www.reso-m.fr/61-lignes-et-horaires.htm) et [métadonnées des lignes](https://data.mobilites-m.fr/api/routers/default/index/routes).

La base dérivée publiée `arrets.json` et le rapport `correspondances.csv` sont proposés sous [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), avec attribution aux producteurs. Les points sélectionnés, altitudes et icônes proviennent des deux KMZ fournis par l’utilisateur. Cette présentation CAF est indépendante des réseaux. Les fiches officielles et PDF externes restent sur les sites de leurs éditeurs et ne sont pas recopiés.

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

Les dossiers contiennent seulement les points de la sélection initiale à partir de 600 m : **ils ne représentent pas tous les arrêts de chaque ligne**, notamment dans la vallée. Aucun tracé d’itinéraire n’est dessiné. Le classement par ligne est figé dans le fichier importé, tandis que les fiches liées sont actualisées quotidiennement. Aucune réimportation quotidienne n’est nécessaire pour consulter les fiches à jour.
