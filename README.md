# **Projet : Prototype d'archivage automatique des logiciels bioinformatiques publiés dans bioRxiv**

## **Description**

Ce projet tutoré est réalisé dans le cadre de mon Master 1 en Bioinformatique à l'Université Paris Cité, sous la supervision de M. Pierre Poulain. Il a pour objectif d'automatiser l'archivage des logiciels bioinformatiques publiés dans les articles bioRxiv, en identifiant les articles pertinents, en extrayant les URLs des dépôts logiciels (comme GitHub ou GitLab), en vérifiant si ces logiciels sont déjà archivés dans **Software Heritage**, et en procédant à leur archivage si nécessaire.

Ce projet vise à garantir la conservation à long terme des logiciels scientifiques en bioinformatique, en utilisant l'API de Software Heritage pour assurer que ces dépôts restent accessibles même si les plateformes de développement d'origine deviennent indisponibles.

Pour une meilleure organisation, j’ai développé un module tools.py qui regroupe toutes les fonctions auxiliaires du projet (création de la base de données, vérification et soumission des dépôts à Software Heritage, gestion des requêtes, etc.).

## **Étapes du projet**

**Le projet est structuré en quatre scripts principaux qui couvrent l’ensemble des étapes de collecte, traitement et archivage des dépôts logiciels bioinformatiques.**

**Script 1 : Extraction des Articles Pertinents**
   
1. **Scraper bioRxiv pour identifier les articles liés à la bioinformatique :**
   
   •	Utilisation de BeautifulSoup et requests pour extraire les articles liés à la collection “bioinformatics” sur bioRxiv.
   
   •	Stockage des informations des articles (titre, lien, DOI, abstract) dans une base de données SQLite pour un suivi ultérieur.

   
**Script 2 : Extraction et Validation des URLs de Dépôts**

1. **Extraire les URLs des dépôts logiciels des abstracts ou des fichiers PDF.**

	•	Recherche des URLs dans les abstracts des articles pour identifier les dépôts logiciels (par exemple, GitHub, GitLab).

	•	Si l’URL n’est pas présente dans l’abstract, un module d’analyse est appliqué au fichier PDF pour détecter les liens.

2. **Vérifier la validité des URLs.**

	•	S’assurer que chaque URL extraite est valide et correspond bien à un dépôt logiciel actif.

3. **Marquer l’état de vérification des articles.**

	•	Mise à jour de la base de données avec une colonne is_article_processed pour indiquer les articles dont les URLs ont été vérifiées, ce qui permet d’éviter de traiter plusieurs fois le même article.



**Script 3 : Archivage et Suivi des Dépôts dans Software Heritage**
   
1. **Vérification de l’archivage dans Software Heritage.**
   
	•	Utilisation de l’API de Software Heritage pour vérifier si le dépôt logiciel est déjà archivé.

	•	Récupération de la date et du lien de l’archive si le dépôt est archivé, pour mise à jour dans les colonnes date_last_archive et url_archive de la base de données.

2. **Archivage des dépôts non archivés.**

	•	Pour les dépôts non archivés, une demande d’archivage est soumise via l’API.

4. **Optimisation du quota d’API.**

	•	Limitation des requêtes pour éviter les erreurs dues au quota d’API (ex. erreur 429). Si l’archive est déjà vérifiée ou le dépôt déjà archivé, aucune requête supplémentaire n’est envoyée.

	•	Utilisation de pauses entre les requêtes pour éviter le dépassement du quota.

**Script 4 : Re-vérification de l’Archivage des Dépôts**

1. **Re-vérification des dépôts soumis pour archivage:**
   
	•	Ce script re-vérifie l’état des dépôts en attente (is_archived_in_swh = 2) pour confirmer leur archivage effectif dans Software Heritage.

	•	Les dépôts confirmés archivés sont mis à jour avec le lien et la date d’archivage.

## **Guide pour Lancer les Scripts**

Avant d’exécuter les scripts, suivez les étapes ci-dessous pour configurer l’environnement et les dépendances.

**1. Installation des Bibliothèques**

Installez les bibliothèques nécessaires avec la commande suivante : 

```bash
pip install requests beautifulsoup4 PyPDF2 pdfplumber
```

**2. Récupération du Token API Software Heritage**

Créez un compte sur Software Heritage pour générer un token API sur le site de Software Heritage (https://archive.softwareheritage.org/). Le token est requis pour soumettre les dépôts à l’archivage. 

Placez ce token dans la variable TOKEN du script 3.

```bash
TOKEN = "votre_token_api"
```

**3. Exécution des Scripts**

Le projet est structuré autour d’un fichier tools.py qui contient toutes les fonctions nécessaires et d’un fichier Jupyter Notebook projet_final.ipynb, où les étapes du projet sont organisées et exécutées de manière interactive.

Étapes pour exécuter le projet :

1.	**Configuration initiale :**
	
	•	Assurez-vous que le fichier tools.py et le fichier projet_final.ipynb sont placés dans le même répertoire.


2.	**Lancer Jupyter Notebook :**
   
	•	Ouvrez un terminal et exécutez la commande suivante :
  
```bash
jupyter notebook
```

•	Dans l’interface qui s’ouvre, localisez et ouvrez le fichier projet_final.ipynb.

3.	**Exécution des étapes dans le Notebook :**

Le fichier projet_final.ipynb est organisé en cellules, chacune correspondant à une étape spécifique du projet :

•	Étape 1 : Extraction des articles depuis bioRxiv – Appel des fonctions pour scraper les articles et stocker les métadonnées dans une base SQLite.
 
 •	Étape 2 : Extraction et validation des URLs des dépôts logiciels – Appel des fonctions pour analyser les abstracts et les PDF pour détecter les dépôts logiciels.

•	Étape 3 : Archivage des dépôts logiciels avec Software Heritage – Vérification et archivage des dépôts via l’API de Software Heritage.

•	Étape 4 : Re-vérification de l’état des dépôts soumis – Vérification périodique des dépôts soumis pour archivage.


Exécutez chaque cellule dans l’ordre pour accomplir toutes les étapes du projet.
	
 4.	**Personnalisation et gestion des erreurs :**

•	Le Notebook permet de personnaliser les paramètres tels que le nombre de pages à scraper, les délais entre les requêtes, ou encore les tokens API.

•	Les journaux d’exécution (logging) affichent en temps réel les informations sur chaque étape, facilitant le suivi et le débogage.

## **Compétences développées**
- **Scraping Web** :  Extraction automatisée de données depuis bioRxiv en utilisant BeautifulSoup et requests pour parcourir les pages web et récupérer des informations d’articles scientifiques pertinents en bioinformatique.
- **Expressions régulières** : Utilisation d’expressions régulières pour détecter et extraire efficacement les URLs spécifiques des dépôts logiciels dans les résumés des articles et les fichiers PDF, garantissant une collecte complète et ciblée des liens logiciels.
- **Manipulation d'API** : Utilisation avancée de l’API de Software Heritage pour vérifier la présence des dépôts logiciels dans leur archive. Cette intégration permet également la soumission automatique des dépôts non archivés pour assurer leur préservation à long terme.
- **Gestion de bases de données avec SQLite** : Conception et gestion d’une base de données SQLite pour stocker les informations clés (titres, liens, et statuts d’archivage des articles), facilitant ainsi le suivi et la gestion des articles analysés et des dépôts logiciels vérifiés ou archivés.
- **Gestion des quotas d’API et optimisation des requêtes** : Implémentation de limites de fréquence pour les requêtes à l’API Software Heritage, en tenant compte des restrictions de taux pour éviter les erreurs de surcharge et pour garantir la fluidité du processus de vérification et d’archivage sur des volumes de données importants.
- **Programmation orientée événement (logging avancé)**: Utilisation de techniques avancées de journalisation pour tracer les événements, signaler les erreurs, et enregistrer les actions à chaque étape du processus, facilitant ainsi le débogage et l’analyse post-traitement.
- **Automatisation de processus répétitifs** :Développement de scripts automatisés pour traiter en continu des lots de données, vérifier l’archivage, et enregistrer les mises à jour dans la base de données, permettant ainsi de traiter efficacement des centaines d’articles et leurs liens logiciels.
- **Développement logiciel collaboratif avec Git et GitHub** :Utilisation de Git pour la gestion de version du code source, ainsi que de GitHub pour le suivi des modifications, la collaboration, et la documentation du projet. Ce processus améliore la traçabilité des développements et facilite la gestion des versions du projet.


## **Auteur**
**MANOUR Inès**, étudiant en Master 1 Bioinformatique à l'Université Paris Cité.

## **Encadrant**
Ce projet est tutoré par **M. Pierre Poulain**, enseignant-chercheur en bioinformatique au :   Laboratoire de Biochimie Théorique  
                                                                                                Institut de Biologie Physico-Chimique  
                                                                                                13 rue Pierre et Marie Curie  
                                                                                                75005 Paris, France
