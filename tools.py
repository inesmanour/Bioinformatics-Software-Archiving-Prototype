#installations

# Imports internes
import io
from io import BytesIO
import logging
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Tuple

# Imports externes 
import pdfplumber
import requests
from bs4 import BeautifulSoup
import urllib.parse

# Constants
VALID_CODE_REPO = ("github.com", "gitlab.com")
MAX_RETRIES = 3
WAIT_INTERVAL = 5  # secondes entre les tentatives pour limiter les erreurs dues au quota d'API

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Fonctions utilitaires pour la base de données
def create_db(db_name="bioinformatics_article.db"):
    """Crée la base de données SQLite avec les tables requises."""
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Création des tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            doi TEXT UNIQUE,
            date TEXT,
            pdf_link TEXT,
            abstract TEXT,
            is_article_processed INTEGER DEFAULT 0,
            contains_valid_repo_link INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS code_repositories (
            code_repo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_repo_url TEXT,
            is_archived_in_swh INTEGER DEFAULT 0,
            swh_archive_link TEXT,
            swh_date_last_archive TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles_code_repositories (
            article_id INTEGER,
            code_repo_id INTEGER,
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (code_repo_id) REFERENCES code_repositories(code_repo_id)
        )
    ''')

    conn.commit()
    logging.info("Base de données créée et initialisée avec succès.")
    return conn, c


def close_db(conn):
    """Ferme la connexion à la base de données."""
    conn.close()
    logging.info("Connexion à la base de données fermée.")


def show_tables(db_name="bioinformatics_article.db"):
    """Affiche les tables et colonnes de la base de données SQLite."""
    conn, c = create_db(db_name)
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    for table in tables:
        logging.info(f"Table: {table[0]}")
        c.execute(f"PRAGMA table_info({table[0]})")
        columns = c.fetchall()
        logging.info(f"Colonnes de {table[0]}: {columns}")
    close_db(conn)

# Fonction pour scraper les articles
def scrape_articles(total_pages=10, db_name="bioinformatics_article.db"):
    """
    Scrape les articles bioRxiv et les enregistre dans la base de données.
    """
    url = 'https://www.biorxiv.org'
    conn, c = create_db(db_name)

    for page in range(1, total_pages + 1):
        logging.info(f"Scraping page {page} sur {total_pages}")
        response = requests.get(f'{url}/collection/bioinformatics?page={page}')
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = soup.find_all('a', class_='highwire-cite-linked-title')

        for article in articles:
            title = article.text.strip()
            link = url + article['href']

            article_response = requests.get(link)
            article_soup = BeautifulSoup(article_response.content, 'html.parser')

            doi_tag = article_soup.find('meta', {'name': 'citation_doi'})
            doi = doi_tag['content'] if doi_tag else 'DOI non disponible'

            c.execute("SELECT * FROM articles WHERE doi = ?", (doi,))
            if c.fetchone():
                logging.info(f"L'article avec DOI {doi} existe déjà dans la base.")
                close_db(conn)
                return  # Stoppe le scraping si les articles sont déjà présents

            date_tag = article_soup.find('meta', {'name': 'citation_publication_date'})
            date = date_tag['content'] if date_tag else 'Date non disponible'
            if date != 'Date non disponible':
                date = date.replace('/', '-')
                date = datetime.strptime(date, '%Y-%m-%d').date().isoformat()

            pdf_links = article_soup.find_all('a')
            pdf_link = next((url + pdf['href'] for pdf in pdf_links if 'PDF' in pdf.text and pdf['href'].endswith('.pdf')), 'Lien PDF non disponible')

            abstract_tag = article_soup.find('meta', {'name': 'citation_abstract'})
            if abstract_tag:
                raw_abstract = abstract_tag['content']
                clean_abstract = BeautifulSoup(raw_abstract, "html.parser").get_text()
            else:
                clean_abstract = 'Abstract non disponible'

            c.execute('''
                INSERT INTO articles (title, link, doi, date, pdf_link, abstract)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, link, doi, date, pdf_link, clean_abstract))
            logging.info(f"Article ajouté : {title}")
            conn.commit()

            time.sleep(1)

    close_db(conn)
# Fonctions pour extraire et gérer les URLs
def extract_repository_urls(text: str) -> set:
    """
    Extrait les URLs des dépôts logiciels (GitHub ou GitLab) d'un texte donné.

    La regex utilisée détecte toutes les chaînes qui commencent par http ou https
    suivies d'un domaine et d'un chemin. Les URLs extraites sont nettoyées et
    filtrées pour inclure uniquement celles appartenant à GitHub ou GitLab.

    Args:
        text (str): Texte à analyser pour les URLs.

    Returns:
        set: Un ensemble de liens valides vers GitHub ou GitLab.
    """
    # Détecte les URLs : commence par http(s):// et capture tout jusqu'à un espace
    url_pattern = r"(https?://[^\s]+)"
    urls = re.findall(url_pattern, text)
    # Nettoie les URLs des caractères indésirables
    cleaned_urls = {url.strip(").,;[]{}") for url in urls if is_valid_code_repo(url)}
    return cleaned_urls

def is_valid_code_repo(link: str) -> bool:
    """Vérifie si un lien appartient à GitHub ou GitLab."""
    return any(code_repo in link for code_repo in VALID_CODE_REPO)


def is_valid_url(url: str) -> bool:
    """
    Vérifie si une URL est valide et accessible.

    Args:
        url (str): L'URL à vérifier.

    Returns:
        bool: True si l'URL est accessible, False sinon.
    """
    try:
        response = requests.head(url, timeout=5)
        if response.status_code == 200:
            return True
        else:
            logging.warning(f"L'URL {url} a retourné le code HTTP {response.status_code}")
            return False
    except requests.RequestException as e:
        logging.error(f"Erreur lors de la vérification de l'URL {url}: {e}")
        return False


def extract_links_from_pdf(pdf_url: str) -> set:
    """
    Extrait les URLs des dépôts logiciels d'un fichier PDF accessible via une URL.

    Args:
        pdf_url (str): Lien direct vers le fichier PDF.

    Returns:
        set: Ensemble de liens valides extraits du PDF.
    """
    repo_urls = set()
    try:
        response = requests.get(pdf_url, timeout=10)
        response.raise_for_status()
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    repo_urls.update(extract_repository_urls(text))
    except Exception as e:
        logging.error(f"Erreur lors de l'extraction des liens du PDF {pdf_url}: {e}")
    return repo_urls

def extract_repository_links(db_name="bioinformatics_article.db"):
    """
    Extrait les URLs des dépôts logiciels (GitHub ou GitLab) d'un texte donné.

    La regex utilisée détecte toutes les chaînes qui commencent par http ou https
    suivies d'un domaine et d'un chemin. Exemple de regex :
        (https?://[^\s]+)
    - https? : Capture http ou https.
    - :// : Obligatoire après http ou https.
    - [^\s]+ : Capture tous les caractères jusqu'à un espace.

    Args:
        text (str): Texte à analyser pour les URLs.

    Returns:
        set: Un ensemble de liens valides vers GitHub ou GitLab.
    """
    conn, c = create_db(db_name)
    c.execute("SELECT id, title, abstract, pdf_link FROM articles WHERE is_article_processed = 0")
    articles = c.fetchall()
    close_db(conn)  # Fermez la connexion principale avant de démarrer les threads

    # Traitement en parallèle des articles
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(lambda article: process_article(article, db_name), articles)

def process_article(article, db_name="bioinformatics_article.db"):
    article_id, title, abstract, pdf_link = article
    logging.info(f"Traitement de l'article '{title}' (ID: {article_id})")

    # Créer une nouvelle connexion SQLite pour ce thread
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Extraction des liens de dépôt
    repo_links = set()
    if abstract:
        repo_links.update(extract_repository_urls(abstract))  # Recherche dans l'abstract
    if pdf_link and pdf_link != 'Lien PDF non disponible':
        repo_links.update(extract_links_from_pdf(pdf_link))  # Recherche dans le PDF

    if repo_links:
        logging.info(f"{len(repo_links)} liens de dépôt trouvés pour l'article '{title}': {repo_links}")
        for repo_url in repo_links:
            try:
                # Insérer le dépôt dans la base
                c.execute("""
                    INSERT OR IGNORE INTO code_repositories (code_repo_url, is_archived_in_swh)
                    VALUES (?, 0)
                """, (repo_url,))
                conn.commit()
                c.execute("SELECT code_repo_id FROM code_repositories WHERE code_repo_url = ?", (repo_url,))
                code_repo_id = c.fetchone()[0]
                
                # Lier le dépôt à l'article
                c.execute("""
                    INSERT OR IGNORE INTO articles_code_repositories (article_id, code_repo_id)
                    VALUES (?, ?)
                """, (article_id, code_repo_id))
                conn.commit()
            except sqlite3.Error as e:
                logging.error(f"Erreur lors de l'insertion ou de la liaison du dépôt '{repo_url}': {e}")
        # Marquer l'article comme contenant des dépôts valides
        c.execute("UPDATE articles SET contains_valid_repo_link = 1 WHERE id = ?", (article_id,))
    else:
        logging.info(f"Aucun lien de dépôt valide trouvé pour l'article '{title}'")

    # Marquer l'article comme traité
    c.execute("UPDATE articles SET is_article_processed = 1 WHERE id = ?", (article_id,))
    conn.commit()

    # Fermer la connexion SQLite
    conn.close()
    time.sleep(1)
    
    
# Fonctions pour gérer les dépôts
def insert_code_repository(conn, repo_url: str) -> Optional[int]:
    """
    Insère un dépôt logiciel dans la base de données et retourne son ID.
    Cette fonction ne fait que l'insertion sans archivage.
    """
    logging.info(f"Tentative d'insertion du dépôt : {repo_url}")
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO code_repositories (code_repo_url, is_archived_in_swh)
            VALUES (?, 0)
        """, (repo_url,))
        conn.commit()
        c.execute("SELECT code_repo_id FROM code_repositories WHERE code_repo_url = ?", (repo_url,))
        result = c.fetchone()
        if result:
            logging.info(f"Dépôt inséré avec succès : {repo_url}, ID : {result[0]}")
            return result[0]
        else:
            logging.warning(f"Le dépôt {repo_url} existe déjà dans la base.")
            return None
    except sqlite3.Error as e:
        logging.error(f"Erreur lors de l'insertion du dépôt {repo_url}: {e}")
        return None
def link_article_to_repo(conn, article_id: int, code_repo_id: int):
    """Crée une association entre un article et un dépôt logiciel."""
    logging.info(f"Tentative de création d'une relation : Article ID {article_id}, Dépôt ID {code_repo_id}")
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO articles_code_repositories (article_id, code_repo_id) VALUES (?, ?)",
                  (article_id, code_repo_id))
        conn.commit()
        logging.info(f"Relation créée avec succès : Article ID {article_id}, Dépôt ID {code_repo_id}")
    except sqlite3.Error as e:
        logging.error(f"Erreur lors de la création du lien article-dépôt : {e}")

# Fonctions pour Software Heritage

# Fonction pour archiver les dépôts
def archive_repositories(db_name="bioinformatics_article.db"):
    """
    Fonction principale pour gérer l'archivage des dépôts logiciels.

    Étapes :
    1. Recherche dans la base de données les dépôts non encore archivés.
    2. Vérifie si le dépôt est déjà archivé dans Software Heritage (via l'API).
    3. Si non archivé, soumet le dépôt pour archivage.
    4. Effectue ces opérations en parallèle grâce à ThreadPoolExecutor.

    Args:
        db_name (str): Nom de la base de données SQLite à utiliser.

    Returns:
        None
    """
    conn, c = create_db(db_name)
    c.execute("SELECT code_repo_id, code_repo_url FROM code_repositories WHERE is_archived_in_swh = 0")
    repos = c.fetchall()
    logging.info(f"Nombre de dépôts à traiter : {len(repos)}")

    if not repos:
        logging.info("Aucun dépôt à traiter. Fin du script.")
        close_db(conn)
        return

    close_db(conn)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_repo, db_name, repo): repo for repo in repos}
        for future in as_completed(futures):
            repo = futures[future]
            try:
                result = future.result()
                logging.info(f"Thread terminé avec succès pour le dépôt : {repo}")
            except Exception as e:
                logging.error(f"Erreur dans le traitement du dépôt {repo}: {e}")



def process_repo(db_name, repo):
    """
    Fonction utilisée par chaque thread pour traiter un dépôt.
    """
    
    # Chaque thread doit ouvrir sa propre connexion SQLite
    conn, c = create_db(db_name)
    code_repo_id, code_repo_url = repo
    logging.info(f"Vérification de l'archivage pour le dépôt : {code_repo_url}")

    try:
        for attempt in range(MAX_RETRIES):
            is_archived, archive_date, archive_link = check_archived(code_repo_url)
            logging.info(f"Résultats pour {code_repo_url}: is_archived={is_archived}, archive_date={archive_date}, archive_link={archive_link}")

            # Si l'URL retourne une 404, arrêtez les tentatives
            if is_archived is None and attempt == 0:
            
                logging.warning(f"Dépôt non trouvé dans Software Heritage. Tentative d'archivage pour : {code_repo_url}")
                archived = archive_repo(code_repo_url, token="your_api_token_here")
                if archived:
                    logging.info(f"Dépôt soumis avec succès pour archivage : {code_repo_url}")
                    c.execute("UPDATE code_repositories SET is_archived_in_swh = 2 WHERE code_repo_id = ?", (code_repo_id,))
                else:
                    logging.error(f"Échec de la soumission pour le dépôt {code_repo_url}")

            if is_archived:
                logging.info(f"Dépôt déjà archivé. Mise à jour des informations pour le dépôt {code_repo_url}")
                c.execute("""
                    UPDATE code_repositories
                    SET is_archived_in_swh = 1, swh_archive_link = ?, swh_date_last_archive = ?
                    WHERE code_repo_id = ?
                """, (archive_link, archive_date, code_repo_id))
            else:
                archived = archive_repo(code_repo_url, token="eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJhMTMxYTQ1My1hM2IyLTQwMTUtODQ2Ny05MzAyZjk3MTFkOGEifQ.eyJpYXQiOjE3MzI4MTIyMDYsImp0aSI6Ijk3ODhmYzIxLTY4NDUtNDYzYi05ZDNmLWM4Y2U3ZDU0NjllMCIsImlzcyI6Imh0dHBzOi8vYXV0aC5zb2Z0d2FyZWhlcml0YWdlLm9yZy9hdXRoL3JlYWxtcy9Tb2Z0d2FyZUhlcml0YWdlIiwiYXVkIjoiaHR0cHM6Ly9hdXRoLnNvZnR3YXJlaGVyaXRhZ2Uub3JnL2F1dGgvcmVhbG1zL1NvZnR3YXJlSGVyaXRhZ2UiLCJzdWIiOiI0NTFmMTkzNy04ZTY4LTQxNjItYTk2Ny1lMjJkZjcwNDc5MmUiLCJ0eXAiOiJPZmZsaW5lIiwiYXpwIjoic3doLXdlYiIsInNlc3Npb25fc3RhdGUiOiI2MjRiOThlMS1hMWQwLTQwZmQtYmM1My03OWMzYmNhMDVjMmQiLCJzY29wZSI6Im9wZW5pZCBvZmZsaW5lX2FjY2VzcyBwcm9maWxlIGVtYWlsIn0.-gIPWBJG-6YmqtbzS33Zn0hNA-dhyKmlAzXD12JIw_w")
                if archived:
                    logging.info(f"Dépôt soumis pour archivage : {code_repo_url}")
                    c.execute("UPDATE code_repositories SET is_archived_in_swh = 2 WHERE code_repo_id = ?", (code_repo_id,))
                else:
                    logging.error(f"Échec de la soumission pour le dépôt {code_repo_url}")

            conn.commit()
            break
    except Exception as e:
        logging.error(f"Erreur lors du traitement du dépôt {code_repo_url}: {e}")
    finally:
        close_db(conn)
        
def clean_url(url: str) -> str:
    """Nettoie une URL en supprimant les caractères non nécessaires à la fin."""
    return url.strip().rstrip('/.').rstrip('?')

def check_archived(repo_url: str) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Vérifie si un dépôt est archivé dans Software Heritage."""
    repo_url = clean_url(repo_url)  # Nettoyage de l'URL avant traitement
    base_url = "https://archive.softwareheritage.org/api/1/origin/"
    encoded_url = urllib.parse.quote(repo_url, safe='')
    check_url = f"{base_url}{encoded_url}/get/"
    
    try:
        response = requests.get(check_url, timeout=10)
        response.raise_for_status()  # Lève une erreur si le statut HTTP est >= 400
        archive_info = response.json()
        
        # Vérifie si des informations d'archive sont disponibles
        if 'origin_visits_url' in archive_info:
            visit_response = requests.get(archive_info['origin_visits_url'], timeout=10)
            visit_response.raise_for_status()
            visit_info = visit_response.json()
            
            # Récupère la dernière visite (archivage)
            if visit_info:
                last_visit = visit_info[0]
                last_archive_date = last_visit.get('date')
                archive_link = f"https://archive.softwareheritage.org/browse/origin/{encoded_url}/"
                return True, last_archive_date, archive_link
        
        # Dépôt archivé mais sans informations de visites
        return True, None, None
    
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logging.error(f"L'URL {repo_url} n'est pas trouvée dans l'API Software Heritage.")
        else:
            logging.error(f"Erreur HTTP pour {repo_url}: {e.response.status_code}, Message: {e.response.text}")
        return None, None, None
    
    except requests.RequestException as e:
        logging.error(f"Erreur de requête pour {repo_url}: {e}")
        return None, None, None

def archive_repo(repo_url: str, token: str) -> bool:
    """Soumet un dépôt pour archivage."""
    repo_url = clean_url(repo_url)  # Nettoyage de l'URL avant soumission
    visit_type = "git"
    encoded_url = urllib.parse.quote(repo_url, safe='')
    save_url = f"https://archive.softwareheritage.org/api/1/origin/save/{visit_type}/url/{encoded_url}/"
    headers = {'Authorization': f'Bearer {token}'}

    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(save_url, headers=headers, timeout=10)
            if response.status_code == 200:
                logging.info(f"Le dépôt {repo_url} a été soumis pour archivage avec succès.")
                return True
            elif response.status_code == 429:  # Trop de requêtes
                wait_time = WAIT_INTERVAL * (retries + 1)
                logging.warning(f"Trop de requêtes. Pause de {wait_time} secondes avant de réessayer.")
                time.sleep(wait_time)
                retries += 1
            else:
                logging.error(f"Erreur lors de la soumission {repo_url}: Code HTTP {response.status_code}, Message: {response.text}")
                return False
        except requests.RequestException as e:
            logging.error(f"Erreur lors de la soumission de {repo_url}: {e}")
            retries += 1
            time.sleep(WAIT_INTERVAL)
    
    logging.error(f"Échec complet de la soumission pour le dépôt {repo_url} après {MAX_RETRIES} tentatives.")
    return False

def recheck_archived_repositories(db_name="bioinformatics_article.db"):
    """
    Re-vérifie les dépôts marqués comme en cours d'archivage dans Software Heritage.
    """
    # Connexion à la base de données pour récupérer les dépôts
    conn, c = create_db(db_name)
    c.execute("SELECT code_repo_id, code_repo_url FROM code_repositories WHERE is_archived_in_swh = 2")
    repos = c.fetchall()
    logging.info(f"Nombre de dépôts à re-vérifier : {len(repos)}")
    logging.info(f"Re-vérification des dépôts marqués comme en cours d'archivage.")
    close_db(conn)  # Fermez la connexion principale pour éviter les conflits

    # Utilisation d'un ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_repo = {executor.submit(process_repo_for_recheck, db_name, repo): repo for repo in repos}
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"Erreur lors de la re-vérification du dépôt {repo[1]}: {e}")

def process_repo_for_recheck(db_name, repo):
    """
    Fonction utilisée pour re-vérifier un dépôt.
    """
    # Chaque thread doit ouvrir sa propre connexion SQLite
    conn, c = create_db(db_name)
    code_repo_id, code_repo_url = repo
    logging.info(f"Re-vérification de l'archivage pour le dépôt : {code_repo_url}")

    try:
        is_archived, archive_date, archive_link = check_archived(code_repo_url)
        if is_archived:
            logging.info(f"Dépôt archivé après soumission. Mise à jour pour le dépôt {code_repo_url}")
            c.execute(
                "UPDATE code_repositories SET is_archived_in_swh = 1, swh_archive_link = ?, swh_date_last_archive = ? WHERE code_repo_id = ?",
                (archive_link, archive_date, code_repo_id)
            )
        conn.commit()
    except Exception as e:
        logging.error(f"Erreur lors de la re-vérification du dépôt {code_repo_url}: {e}")
    finally:
        close_db(conn)