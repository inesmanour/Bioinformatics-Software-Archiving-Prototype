# **Projet : Prototype d'archivage automatique des logiciels bioinformatiques publiés dans bioRxiv**

## **Description**
Ce projet tutoré est réalisé dans le cadre de mon Master 1 en Bioinformatique à l'Université Paris Cité, sous la supervision de M. Pierre Poulain. Il a pour objectif d'automatiser l'archivage des logiciels bioinformatiques publiés dans les articles bioRxiv, en identifiant les articles pertinents, en extrayant les URLs des dépôts logiciels (comme GitHub ou GitLab), en vérifiant si ces logiciels sont déjà archivés dans **Software Heritage**, et en procédant à leur archivage si nécessaire.

Ce projet vise à garantir la conservation à long terme des logiciels scientifiques en bioinformatique, en utilisant l'API de Software Heritage pour assurer que ces dépôts restent accessibles même si les plateformes de développement d'origine deviennent indisponibles.

## **Étapes du projet**

1. **Scraper bioRxiv pour identifier les articles liés à la bioinformatique :**
   - Utilisation de **BeautifulSoup** et **requests** pour extraire les articles liés à la collection "bioinformatics" sur bioRxiv.
   

2. **Extraire les URLs des dépôts logiciels dans les abstracts ou les fichiers PDF :**
   - Analyser les abstracts des articles à la recherche de liens vers des dépôts logiciels (GitHub, GitLab, etc.).
   - Si l'URL n'est pas présente dans l'abstract, examiner les fichiers PDF des articles pour y trouver des liens.

3. **Vérifier la validité de ces URLs :**
   - Pour chaque URL trouvée, s'assurer qu'elle est valide et accessible.
   - Tester si l'URL pointe vers un dépôt logiciel actif (par exemple, un dépôt GitHub ou GitLab valide).

4. **Tester si le code source est déjà archivé dans Software Heritage :**
   - Utiliser l'API de **Software Heritage** pour vérifier si le dépôt logiciel est déjà archivé dans leur base de données.
   - Si l'archive existe déjà, ignorer l'étape suivante.

5. **Soumettre les dépôts non archivés pour archivage automatique dans Software Heritage :**
   - Si le dépôt n'est pas trouvé dans Software Heritage, soumettre automatiquement une demande d'archivage en utilisant l'API.

## **Compétences développées**
- **Scraping Web** : Extraction de données à partir de pages web avec BeautifulSoup et requests.
- **Expressions régulières** : Utilisées pour rechercher des URL spécifiques dans les abstracts et les fichiers PDF.
- **Manipulation d'API** : Utilisation de l'API de Software Heritage pour vérifier l'archivage et soumettre de nouveaux dépôts.
- **Base de données SQLite** : Stockage des titres et liens des articles pertinents dans une base de données locale pour un suivi efficace.
- **Développement logiciel avec Git et GitHub** : Suivi des versions et collaboration sur le projet à l'aide de git et GitHub.

## **Auteur**
**MANOUR Inès**, étudiant en Master 1 Bioinformatique à l'Université Paris Cité.

## **Encadrant**
Ce projet est tutoré par **M. Pierre Poulain**, enseignant-chercheur en bioinformatique au :   Laboratoire de Biochimie Théorique  
                                                                                                Institut de Biologie Physico-Chimique  
                                                                                                13 rue Pierre et Marie Curie  
                                                                                                75005 Paris, France
