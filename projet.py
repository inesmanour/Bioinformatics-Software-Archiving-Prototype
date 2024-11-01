## Installation de bibliotheques 

#pip install beautifulsoup4

#pip install requests

#pip install PyPDF2

#pip install pdfplumber


import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from datetime import datetime

import pdfplumber
import re, io
import PyPDF2
from io import BytesIO
import os

import time
from threading import Timer

import logging
import urllib.parse


''' 1  Scraper les articles bioRxiv liés à la bioinformatique '''

url = 'https://www.biorxiv.org'

# Créer la base de données SQLite "bioinformatics_articles"
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor()

# Créer la table 'articles' si elle n'existe pas
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             title TEXT, 
             link TEXT,
             doi TEXT UNIQUE,
             date TEXT,
             pdf_link TEXT,
             abstract TEXT)''')

# Nombre de pages à scraper (exemple : 10 pages à la fois)
total_pages = 10

# Boucle qui parcourt chaque page de la collection Bioinformatics
for page in range(1, total_pages + 1):
    print(f"Scraping page {page} sur {total_pages}")

    # Requête qui récupère la page bioinfo actuelle
    response = requests.get(f'{url}/collection/bioinformatics?page={page}')
    soup = BeautifulSoup(response.content, 'html.parser')

    # Trouver les liens vers les articles sur cette page
    articles = soup.find_all('a', class_='highwire-cite-linked-title')

    print(f'Nombre total d\'articles trouvés sur la page {page} : {len(articles)}')

    # Parcourir tous les articles de la page et enregistrer leurs titres et liens
    for article in articles:
        title = article.text.strip()
        link = url + article['href']

        # Requête pour accéder à la page de l'article
        article_response = requests.get(link)
        article_soup = BeautifulSoup(article_response.content, 'html.parser')

        # Extraire le DOI
        doi_tag = article_soup.find('meta', {'name': 'citation_doi'})
        doi = doi_tag['content'] if doi_tag else 'DOI non disponible'

        # Extraire la date de publication
        date_tag = article_soup.find('meta', {'name': 'citation_publication_date'})
        date = date_tag['content'] if date_tag else 'Date non disponible'
        if date != 'Date non disponible':
            date = date.replace('/', '-')  # Remplacer '/' par '-'
            date = datetime.strptime(date, '%Y-%m-%d').date().isoformat()

        # Extraire le lien vers le fichier PDF
        pdf_links = article_soup.find_all('a')
        pdf_link = next((url + pdf['href'] for pdf in pdf_links if 'PDF' in pdf.text and pdf['href'].endswith('.pdf')), 'Lien PDF non disponible')

        # Extraire l'abstract
        abstract_tag = article_soup.find('meta', {'name': 'citation_abstract'})
        clean_abstract = abstract_tag['content'] if abstract_tag else 'Abstract non disponible'

        # Supprimer les balises <p> au début et à la fin de l'abstract
        if clean_abstract.startswith('<p>'):
            clean_abstract = clean_abstract[3:]  # Supprimer les 3 premiers caractères
        if clean_abstract.endswith('</p>'):
            clean_abstract = clean_abstract[:-4]  # Supprimer les 4 derniers caractères

        # Insérer dans la base de données SQLite
        c.execute("SELECT * FROM articles WHERE doi = ? AND date = ?", (doi, date))
        result = c.fetchone()

        if result:
            print(f"L'article avec DOI {doi} existe déjà, ignoré.")
        else:
            c.execute("INSERT INTO articles (title, link, doi, date, pdf_link, abstract) VALUES (?, ?, ?, ?, ?, ?)", 
                      (title, link, doi, date, pdf_link, clean_abstract))
            print(f"Article ajouté : {title}")

        time.sleep(1)

    # Sauvegarder les modifications dans la base de données après chaque page
    database.commit()
    
database.close()

    
    
    
    
    
''' 2. Extraire les URLs des dépôts logiciels dans les abstracts ou les fichiers PDF 


1.	Vérification et ajout des colonnes nécessaires dans la base de données.

2.	Validation des liens pour s’assurer qu’ils sont valides et pertinents.

3.	Vérification de l’accessibilité des URLs via des requêtes HTTP.

4.	Extraction des URLs des dépôts à partir des contenus des PDF et des abstracts.

5.	Traitement des nouveaux articles non encore traités pour l’extraction.'''



# Connexion à la base de données SQLite
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor()

# Vérifier et ajouter les colonnes software_links et is_article_processed si elles n'existent pas
try:
    c.execute("ALTER TABLE articles ADD COLUMN software_links TEXT")
except sqlite3.OperationalError:
    pass  # La colonne existe déjà

try:
    c.execute("ALTER TABLE articles ADD COLUMN is_article_processed INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass  # La colonne existe déjà

# Fonction pour vérifier si un lien est valide et s'il est un lien GitHub ou GitLab
def is_valid_link(link):
    return link.startswith('http://') or link.startswith('https://')

def is_github_or_gitlab(link):
    return 'github.com' in link or 'gitlab.com' in link

# Fonction pour nettoyer les liens partiels ou incorrects
def clean_link(link):
    link = link.strip(').;,[]')  # Supprimer les caractères indésirables
    if is_valid_link(link) and len(link) > len('https://github.com/'):
        return link
    return None

# Fonction pour tester la validité des URLs via une requête HTTP
def check_url_validity(link):
    try:
        response = requests.get(link, timeout=10)
        if response.status_code == 200:
            print(f"Le lien est valide : {link}")
            return True
        else:
            print(f"Le lien a retourné un code de statut {response.status_code} pour : {link}")
            return False
    except requests.RequestException:
        print(f"Erreur lors de la vérification du lien : {link}")
        return False

# Fonction pour extraire les URLs des dépôts logiciels
def extract_repository_urls(text):
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, text)
    repo_urls = []

    for url in urls:
        cleaned_url = clean_link(url)
        if cleaned_url and is_github_or_gitlab(cleaned_url):
            if check_url_validity(cleaned_url):  # Vérification de l'URL avant de l'ajouter
                repo_urls.append(cleaned_url)

    return repo_urls

# Fonction pour extraire les liens de dépôt logiciel
def extract_software_links(article_id, pdf_link, abstract):
    software_links_set = set()

    # Extraction des liens depuis le PDF
    if pdf_link and pdf_link != 'Lien PDF non disponible':
        try:
            print(f"Ouverture du PDF pour l'article {article_id}: {pdf_link}")
            response = requests.get(pdf_link)
            response.raise_for_status()

            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                print(f"Le PDF a été ouvert avec succès pour l'article {article_id}. Recherche de liens...")
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        links_from_pdf = extract_repository_urls(text)
                        if links_from_pdf:
                            software_links_set.update(links_from_pdf)
                            print(f"Liens trouvés dans le PDF pour l'article {article_id} : {links_from_pdf}")

        except Exception as e:
            print(f"Erreur lors de l'ouverture du PDF pour l'article {article_id}: {e}")

    # Extraction des liens depuis l'abstract
    if abstract and abstract != 'Abstract non disponible':
        print(f"Vérification de l'abstract pour l'article {article_id}.")
        links_from_abstract = extract_repository_urls(abstract)
        if links_from_abstract:
            software_links_set.update(links_from_abstract)
            print(f"Liens trouvés dans l'abstract pour l'article {article_id} : {links_from_abstract}")

    valid_links = [clean_link(link) for link in software_links_set if clean_link(link) and is_github_or_gitlab(link)]

    # Mise à jour de la base de données selon la présence ou non de liens valides
    if valid_links:
        print(f"Liens de dépôt logiciel valides pour l'article {article_id} : {valid_links}")
        c.execute("UPDATE articles SET software_links = ?, is_article_processed = 1 WHERE id = ?", (', '.join(valid_links), article_id))
    else:
        print(f"Aucun lien de dépôt logiciel trouvé pour l'article {article_id}.")
        c.execute("UPDATE articles SET is_article_processed = 2 WHERE id = ?", (article_id,))

    # Enregistrer les modifications dans la base de données
    database.commit()
    time.sleep(1)

# Fonction pour traiter uniquement les nouveaux articles non traités (is_article_processed = 0)
def process_new_articles():
    c.execute("SELECT id, title, pdf_link, abstract FROM articles WHERE is_article_processed = 0")
    articles_to_process = c.fetchall()

    # Vérifier s'il y a des articles à traiter
    if not articles_to_process:
        print("Aucun article à traiter.")
    else:
        print(f"{len(articles_to_process)} article(s) trouvé(s) à traiter.")

    for article in articles_to_process:
        article_id, title, pdf_link, abstract = article
        print(f"Traitement de l'article : {title} (ID: {article_id})...")
        extract_software_links(article_id, pdf_link, abstract)

# Appel de la fonction principale
try:
    process_new_articles()
except KeyboardInterrupt:
    print("Traitement interrompu. Les données sont sauvegardées.")
finally:
    database.close()
    
    
    
'''Utiliser ce code lorsqu'un article avec un temps de recherche dans le pdf trop long ,timer définit a 5min et passe après a l'abstract '''


# Connexion à la base de données SQLite
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor()

# Vérifier et ajouter les colonnes software_links et is_article_processed si elles n'existent pas
try:
    c.execute("ALTER TABLE articles ADD COLUMN software_links TEXT")
except sqlite3.OperationalError:
    pass  # La colonne existe déjà

try:
    c.execute("ALTER TABLE articles ADD COLUMN is_article_processed INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass  # La colonne existe déjà

# Fonction pour vérifier si un lien est valide et s'il est un lien GitHub ou GitLab
def is_valid_link(link):
    return link.startswith('http://') or link.startswith('https://')

def is_github_or_gitlab(link):
    return 'github.com' in link or 'gitlab.com' in link

# Fonction pour nettoyer les liens partiels ou incorrects
def clean_link(link):
    link = link.strip(').;,[]')  # Supprimer les caractères indésirables
    if is_valid_link(link) and len(link) > len('https://github.com/'):
        return link
    return None

# Fonction pour tester la validité des URLs via une requête HTTP
def check_url_validity(link):
    try:
        response = requests.get(link, timeout=10)
        if response.status_code == 200:
            print(f"Le lien est valide : {link}")
            return True
        else:
            print(f"Le lien a retourné un code de statut {response.status_code} pour : {link}")
            return False
    except requests.RequestException:
        print(f"Erreur lors de la vérification du lien : {link}")
        return False

# Fonction pour extraire les URLs des dépôts logiciels
def extract_repository_urls(text):
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, text)
    repo_urls = []

    for url in urls:
        cleaned_url = clean_link(url)
        if cleaned_url and is_github_or_gitlab(cleaned_url):
            if check_url_validity(cleaned_url):  # Vérification de l'URL avant de l'ajouter
                repo_urls.append(cleaned_url)

    return repo_urls

# Fonction pour extraire les liens de dépôt logiciel
def extract_software_links(article_id, pdf_link, abstract):
    software_links_set = set()

    # Timer pour contrôler le temps d'attente
    timer = None
    
    def time_up():
        nonlocal timer
        print(f"Temps écoulé pour l'article {article_id}. Passage à l'abstract.")
        timer = None  # Annule le timer

    # Extraction des liens depuis le PDF
    if pdf_link and pdf_link != 'Lien PDF non disponible':
        timer = Timer(300, time_up)  # 60 secondes = 1 minute
        timer.start()

        try:
            print(f"Ouverture du PDF pour l'article {article_id}: {pdf_link}")
            response = requests.get(pdf_link)
            response.raise_for_status()

            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                print(f"Le PDF a été ouvert avec succès pour l'article {article_id}. Recherche de liens...")
                for page in pdf.pages:
                    if timer is None:  # Vérifie si le timer est toujours actif
                        text = page.extract_text()
                        if text:
                            links_from_pdf = extract_repository_urls(text)
                            if links_from_pdf:
                                software_links_set.update(links_from_pdf)
                                print(f"Liens trouvés dans le PDF pour l'article {article_id} : {links_from_pdf}")
                                break  # Sortir de la boucle si des liens sont trouvés
                    else:
                        print("Recherche dans le PDF abandonnée en raison du dépassement de temps.")
                        break

        except Exception as e:
            print(f"Erreur lors de l'ouverture du PDF pour l'article {article_id}: {e}")

        if timer is not None:
            timer.cancel()  # Annuler le timer si l'extraction a réussi

    # Extraction des liens depuis l'abstract
    if not software_links_set and abstract and abstract != 'Abstract non disponible':
        print(f"Vérification de l'abstract pour l'article {article_id}.")
        links_from_abstract = extract_repository_urls(abstract)
        if links_from_abstract:
            software_links_set.update(links_from_abstract)
            print(f"Liens trouvés dans l'abstract pour l'article {article_id} : {links_from_abstract}")

    valid_links = [clean_link(link) for link in software_links_set if clean_link(link) and is_github_or_gitlab(link)]

    # Mise à jour de la base de données selon la présence ou non de liens valides
    if valid_links:
        print(f"Liens de dépôt logiciel valides pour l'article {article_id} : {valid_links}")
        c.execute("UPDATE articles SET software_links = ?, is_article_processed = 1 WHERE id = ?", (', '.join(valid_links), article_id))
    else:
        print(f"Aucun lien de dépôt logiciel trouvé pour l'article {article_id}.")
        c.execute("UPDATE articles SET is_article_processed = 2 WHERE id = ?", (article_id,))

    # Enregistrer les modifications dans la base de données
    database.commit()
    time.sleep(1)

# Fonction pour traiter uniquement les nouveaux articles non traités (is_article_processed = 0)
def process_new_articles():
    c.execute("SELECT id, title, pdf_link, abstract FROM articles WHERE is_article_processed = 0")
    articles_to_process = c.fetchall()

    # Vérifier s'il y a des articles à traiter
    if not articles_to_process:
        print("Aucun article à traiter.")
    else:
        print(f"{len(articles_to_process)} article(s) trouvé(s) à traiter.")

    for article in articles_to_process:
        article_id, title, pdf_link, abstract = article
        print(f"Traitement de l'article : {title} (ID: {article_id})...")
        extract_software_links(article_id, pdf_link, abstract)

# Appel de la fonction principale
try:
    process_new_articles()
except KeyboardInterrupt:
    print("Traitement interrompu. Les données sont sauvegardées.")
finally:
    database.close()
    
    
    
    
''' 3.	Archivage via Software Heritage:'''

## Objectif
#Utiliser l’API de Software Heritage pour vérifier si le dépôt logiciel est déjà archivé dans leur base de données. Si le dépôt n’est pas encore archivé, soumettre automatiquement une demande d’archivage via l’API.


# Configuration du logging pour afficher les informations de journalisation
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fonction pour créer une nouvelle base de données avec les colonnes nécessaires
def create_new_database(db_name="new_bioinformatics_articles.db"):
    # Connexion à la base de données SQLite
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    
    try:
        # Création de la table 'articles' si elle n'existe pas déjà, avec les colonnes requises
        c.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                link TEXT,
                doi TEXT,
                date TEXT,
                pdf_link TEXT,
                abstract TEXT,
                software_links TEXT,
                is_article_processed INTEGER DEFAULT 0,
                date_last_archive TEXT DEFAULT '',
                url_archive TEXT DEFAULT ''
            )
        ''')
        logging.info(f"Nouvelle base de données '{db_name}' créée avec succès avec la table 'articles'.")
    except sqlite3.OperationalError as e:
        # Gestion des erreurs potentielles lors de la création de la table
        logging.error(f"Erreur lors de la création de la base de données : {e}")
    finally:
        # Validation des modifications et fermeture de la connexion
        conn.commit()
        conn.close()

# Appel de la fonction pour créer la nouvelle base de données
create_new_database()

# Connexion à la base de données existante 'bioinformatics_articles.db'
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor()

# Ajouter les colonnes 'date_last_archive' et 'url_archive' si elles n'existent pas déjà
try:
    c.execute("ALTER TABLE articles ADD COLUMN date_last_archive TEXT DEFAULT '';")
    c.execute("ALTER TABLE articles ADD COLUMN url_archive TEXT DEFAULT '';")
    logging.info("Colonnes 'date_last_archive' et 'url_archive' ajoutées avec succès.")
except sqlite3.OperationalError as e:
    # Gestion des erreurs si les colonnes existent déjà
    logging.warning(f"Les colonnes existent peut-être déjà : {e}")

# Token d'API Software Heritage pour les requêtes d'archivage
TOKEN = "votre_token_ici"

# Fonction pour vérifier si un dépôt est déjà archivé dans Software Heritage
def check_archived(depot_url):
    # URL de base pour vérifier l'archivage dans Software Heritage
    base_url = "https://archive.softwareheritage.org/api/1/origin/"
    encoded_url = urllib.parse.quote(depot_url, safe='')
    check_url = f"{base_url}{encoded_url}/get/"

    logging.info(f"Vérification de l'URL : {check_url}")
    try:
        # Requête pour vérifier si le dépôt est archivé
        response = requests.get(check_url)
        response.raise_for_status()
        archive_info = response.json()

        # Si l'URL des visites est présente, on peut vérifier la date d'archivage
        if 'origin_visits_url' in archive_info:
            origin_visits_url = archive_info['origin_visits_url']
            visit_response = requests.get(origin_visits_url)
            visit_response.raise_for_status()
            visit_info = visit_response.json()

            # Extraction de la dernière date d'archivage
            if visit_info and 'date' in visit_info[0]:
                last_visit = visit_info[0]
                last_archive_date = last_visit['date']
                archive_link = f"https://archive.softwareheritage.org/browse/origin/{encoded_url}/"
                logging.info(f"Lien de l'archive : {archive_link}, Date de la dernière archive : {last_archive_date}")
                return True, archive_link, last_archive_date
            else:
                logging.warning("Aucune date d'archivage trouvée.")
                return True, 'Lien non disponible', 'Date non disponible'

        else:
            logging.warning("Les informations d'archive ne contiennent pas de clé 'origin_visits_url'.")
            return True, 'Lien non disponible', 'Date non disponible'

    except requests.RequestException as e:
        # Gestion des erreurs de requête
        logging.error(f"Erreur lors de la vérification de {depot_url} : {e}")
        return None, None, None

# Fonction pour archiver un dépôt sur Software Heritage
def archive_repo(depot_url):
    # Définition du type de visite et encodage de l'URL
    visit_type = "git"
    encoded_url = urllib.parse.quote(depot_url, safe='')
    save_url = f"https://archive.softwareheritage.org/api/1/origin/save/{visit_type}/url/{encoded_url}/"

    headers = {
        'Authorization': f'Bearer {TOKEN}'
    }

    try:
        # Requête pour soumettre l'archivage
        response = requests.post(save_url, headers=headers)
        if response.status_code == 200:
            logging.info(f"Le dépôt {depot_url} a été soumis pour archivage avec succès.")
            return True
        elif response.status_code == 429:
            # Gestion de la limite de requêtes avec une pause de 3 secondes en cas de surcharge
            logging.warning("Erreur 429 : Trop de requêtes. Pause de 3 secondes.")
            time.sleep(3)
            return archive_repo(depot_url)
        else:
            logging.warning(f"Erreur lors de la soumission de {depot_url} : {response.status_code}")
            return False
    except requests.RequestException as e:
        # Gestion des erreurs de requête
        logging.error(f"Erreur lors de la soumission de {depot_url} : {e}")
        return False

# Limites de requêtes par heure pour éviter la surcharge du serveur
MAX_REQUESTS_PER_HOUR = 1200
TIME_BETWEEN_REQUESTS = 3600 / MAX_REQUESTS_PER_HOUR

# Lecture des URLs des dépôts et gestion de l'archivage
def process_repositories():
    # Sélection des articles dont les informations d'archive sont vides
    c.execute("SELECT software_links FROM articles WHERE software_links IS NOT NULL AND date_last_archive = '' AND url_archive = ''")
    rows = c.fetchall()

    for row in rows:
        depot_urls = row[0].split(',')
        
        for depot_url in depot_urls:
            depot_url = depot_url.strip()

            if depot_url and depot_url.startswith("http"):
                # Vérifier si le dépôt est déjà archivé
                is_archived, archive_link, last_archive_date = check_archived(depot_url)

                if is_archived:
                    # Mise à jour des informations d'archivage si le dépôt est déjà archivé
                    c.execute("UPDATE articles SET date_last_archive = ?, url_archive = ? WHERE software_links LIKE ?",
                              (last_archive_date, archive_link, f'%{depot_url}%'))
                    database.commit()
                    logging.info(f"Dépôt déjà archivé : {archive_link} à la date {last_archive_date}")
                else:
                    # Soumettre le dépôt pour archivage s'il n'est pas déjà archivé
                    if archive_repo(depot_url):
                        logging.info(f"Dépôt {depot_url} soumis pour archivage.") 
                    database.commit()    
                    time.sleep(TIME_BETWEEN_REQUESTS)
            else:
                # Gestion des URL invalides
                logging.warning(f"URL invalide trouvée : {depot_url}")

# Exécuter la fonction pour traiter les dépôts
process_repositories()

# Validation finale des modifications et fermeture de la connexion à la base de données
database.commit()
database.close()