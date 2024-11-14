#installations

import sqlite3
import requests
from bs4 import BeautifulSoup
import pdfplumber
import re
import time
import urllib.parse
import io
import logging
from datetime import datetime
import PyPDF2
from io import BytesIO
import os
from threading import Timer
from concurrent.futures import ThreadPoolExecutor

# Constantes de configuration
MAX_RETRIES = 5
WAIT_INTERVAL = 3  # Intervalle d'attente en secondes

# Configuration de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def extract_repository_urls(text):
    """Extrait les URLs des dépôts logiciels (GitHub ou GitLab) d'un texte donné."""
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, text)
    repo_urls = [clean_link(url) for url in urls if clean_link(url) and is_github_or_gitlab(url)]
    return set(repo_urls)

def clean_link(link):
    """Nettoie les liens partiels ou incorrects."""
    link = link.strip(').;,[]')
    if is_valid_link(link) and len(link) > len('https://github.com/'):
        return link
    return None

def is_valid_link(link):
    return link.startswith('http://') or link.startswith('https://')

def is_github_or_gitlab(link):
    return 'github.com' in link or 'gitlab.com' in link

def extract_links_from_pdf(pdf_url):
    """Extrait les liens des dépôts logiciels depuis un PDF."""
    repo_urls = set()
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    repo_urls.update(extract_repository_urls(text))
    except Exception as e:
        logging.error(f"Erreur lors de l'ouverture du PDF {pdf_url}: {e}")
    return repo_urls

def insert_code_repository(conn, repo_url):
    """Insère un dépôt logiciel dans la base de données et retourne son ID."""
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO code_repositories (code_repo_url) VALUES (?)", (repo_url,))
        conn.commit()
        c.execute("SELECT code_repo_id FROM code_repositories WHERE code_repo_url = ?", (repo_url,))
        return c.fetchone()[0]
    except sqlite3.Error as e:
        logging.error(f"Erreur lors de l'insertion du dépôt {repo_url}: {e}")
        return None

def link_article_to_repo(conn, article_id, code_repo_id):
    """Crée une association entre un article et un dépôt logiciel."""
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO articles_code_repositories (article_id, code_repo_id) VALUES (?, ?)", (article_id, code_repo_id))
        conn.commit()
        logging.info(f"Lien créé entre l'article {article_id} et le dépôt {code_repo_id}")
    except sqlite3.Error as e:
        logging.error(f"Erreur lors de la création du lien article-dépôt : {e}")

def check_archived(depot_url):
    """Vérifie si un dépôt est déjà archivé dans Software Heritage."""
    base_url = "https://archive.softwareheritage.org/api/1/origin/"
    encoded_url = urllib.parse.quote(depot_url, safe='')
    check_url = f"{base_url}{encoded_url}/get/"
    
    try:
        response = requests.get(check_url)
        response.raise_for_status()
        archive_info = response.json()
        if 'origin_visits_url' in archive_info:
            visit_response = requests.get(archive_info['origin_visits_url'])
            visit_response.raise_for_status()
            visit_info = visit_response.json()
            if visit_info:
                last_visit = visit_info[0]
                last_archive_date = last_visit.get('date')
                archive_link = f"https://archive.softwareheritage.org/browse/origin/{encoded_url}/"
                return True, last_archive_date, archive_link
        return True, None, None
    except requests.RequestException as e:
        logging.error(f"Erreur lors de la vérification de {depot_url} : {e}")
        return False, None, None



def archive_repo(depot_url, token="eyJhbGciOiJIUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJhMTMxYTQ1My1hM2IyLTQwMTUtODQ2Ny05MzAyZjk3MTFkOGEifQ.eyJpYXQiOjE3MzE1ODc0MTUsImp0aSI6Ijk0MjBjMTRiLTI3MTctNGFjMi1iOGYwLTBjNGJmNjA5MGY5NSIsImlzcyI6Imh0dHBzOi8vYXV0aC5zb2Z0d2FyZWhlcml0YWdlLm9yZy9hdXRoL3JlYWxtcy9Tb2Z0d2FyZUhlcml0YWdlIiwiYXVkIjoiaHR0cHM6Ly9hdXRoLnNvZnR3YXJlaGVyaXRhZ2Uub3JnL2F1dGgvcmVhbG1zL1NvZnR3YXJlSGVyaXRhZ2UiLCJzdWIiOiI0NTFmMTkzNy04ZTY4LTQxNjItYTk2Ny1lMjJkZjcwNDc5MmUiLCJ0eXAiOiJPZmZsaW5lIiwiYXpwIjoic3doLXdlYiIsInNlc3Npb25fc3RhdGUiOiI0ZDNmM2Y2NC1lOTYzLTQzOGMtYjIwYy1mYjI0OWU1ZDgzZjYiLCJzY29wZSI6Im9wZW5pZCBvZmZsaW5lX2FjY2VzcyBwcm9maWxlIGVtYWlsIn0.jVV2Me12WIc1Wc9BwE9_pg0YwBGMuAWS0_3W-oKDS38"):
    """Soumet un dépôt à Software Heritage pour archivage."""
    visit_type = "git"
    encoded_url = urllib.parse.quote(depot_url, safe='')
    save_url = f"https://archive.softwareheritage.org/api/1/origin/save/{visit_type}/url/{encoded_url}/"
    headers = {'Authorization': f'Bearer {token}'}

    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(save_url, headers=headers)
            if response.status_code == 200:
                logging.info(f"Le dépôt {depot_url} a été soumis pour archivage avec succès.")
                return True
            elif response.status_code == 429:
                logging.warning("Trop de requêtes. Pause de quelques secondes.")
                time.sleep(WAIT_INTERVAL)
                retries += 1
            else:
                logging.error(f"Erreur lors de la soumission de {depot_url} : {response.status_code}")
                return False
        except requests.RequestException as e:
            logging.error(f"Erreur lors de la soumission de {depot_url} : {e}")
            retries += 1
            time.sleep(WAIT_INTERVAL)
    return False