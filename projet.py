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



''' Scraper les articles bioRxiv liés à la bioinformatique '''
# URL de base
url = 'https://www.biorxiv.org'

# creer base de données SQLite "bioinformatics_articles" 
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor() #ici le curseur 'c' permettra d'executer/parcourir les requetes SQL sur database


c.execute("DROP TABLE IF EXISTS articles")

# create table 'articles' avec col id,title et le lien 
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             title TEXT, 
             link TEXT,
             doi TEXT UNIQUE,
             date TEXT,
             pdf_link TEXT,
             abstract TEXT)''')
#id c'est un identifiant unique généré automatiquement 


'''parcourir les articles de la collection bio info contenant 2153 pages et enregistrer ces informations'''

## Nombre de pages à scraper (exemple : 10 pages à la fois)
from pickle import TRUE


total_pages = 10

# boucle qui parcour chaque page de la collection Bioinformatics
for page in range(1, total_pages + 1):
    print(f"Scraping page {page} sur {total_pages}")

    # requete qui recup la page bioinfo actuelle
    response = requests.get(f'{url}/collection/bioinformatics?page={page}') #? mean numero de la {page}
    soup = BeautifulSoup(response.content, 'html.parser')

    # Trouver les liens vers les articles sur cette page
    articles = soup.find_all('a', class_='highwire-cite-linked-title')  # find liens hypertextes avec classe CSS

    print(f'Nombre total d\'articles trouvés sur la page {page} : {len(articles)}')

    # Parcourir tous les articles de la page et enregistrer leurs titres et liens
    for article in articles:
        title = article.text.strip()  # extraire le titre dans la balise <a>, accessible via .text.
        link = url + article['href']  # extraire le lien , href=destination du lien de mon article

        # Requête pour accéder à la page de l'article
        article_response = requests.get(link)
        article_soup = BeautifulSoup(article_response.content, 'html.parser')

        # extraire le DOI (dans une balise meta ou dans l'URL)
        doi_tag = article_soup.find('meta', {'name': 'citation_doi'})  # balise <meta> qui a l’attribut name="citation_doi".
        doi = doi_tag['content'] if doi_tag else 'DOI non disponible'  # si balise existe -> attribut content contient la valeur doi

        # extraire la date de publication (dans une balise meta ou time)et la formater au format ISO 8601
        date_tag = article_soup.find('meta', {'name': 'citation_publication_date'})
        date = date_tag['content'] if date_tag else 'Date non disponible'
        # Remplacer les barres obliques par des tirets avant la conversion
        if date != 'Date non disponible':
            date = date.replace('/', '-')  # Remplacer '/' par '-'
            date = datetime.strptime(date, '%Y-%m-%d').date().isoformat()

        # extraire le lien vers le fichier PDF
        pdf_links = article_soup.find_all('a')
        pdf_link = None
        for pdf in pdf_links:
            if pdf and 'PDF' in pdf.text:
                potential_pdf_link = url + pdf['href']
                if potential_pdf_link.endswith('.pdf'):  # Vérifier si le lien se termine par .pdf
                    pdf_link = potential_pdf_link
                    break  # Quitter la boucle une fois le lien trouvé

        # En cas de lien invalide, assigner une valeur par défaut
        if not pdf_link:
            pdf_link = 'Lien PDF non disponible'

        
        
         # Extraire l'abstract
        abstract_tag = article_soup.find('meta', {'name': 'citation_abstract'})
        if abstract_tag:
            abstract_html = abstract_tag['content']
            clean_abstract = BeautifulSoup(abstract_html, "html.parser").get_text(strip=True)
        else:
            clean_abstract = 'Abstract non disponible'


        # tout inserer dans la base de données SQLite
        # Vérifier si l'article existe déjà dans la base de données (vérification sur DOI et date)
        c.execute("SELECT * FROM articles WHERE doi = ? AND date = ?", (doi, date))
        result = c.fetchone() # recupère la 1ere ligne du result donc si mm doi/date trouvé retourne cette ligne en tuple sinon NONE

        if result:
            print(f"L'article avec DOI {doi} existe déjà, ignoré.")
        else:
            # Insérer l'article dans la base de données
            c.execute("INSERT INTO articles (title, link, doi, date, pdf_link, abstract) VALUES (?, ?, ?, ?, ?, ?)", 
                      (title, link, doi, date, pdf_link, clean_abstract))
            print(f"Article ajouté : {title}")

        # Afficher les informations extraites
        #print(f'Titre: {title}\nLien: {link}\nDOI: {doi}\nDate de publication: {date}\nLien PDF: {pdf_link}\nRésumé:{clean_abstract}\n')
        # pause d'une seconde pour éviter de surcharger le serveur
        time.sleep(1)
        
    # Sauvegarder les modifications dans la base de données après chaque page
    database.commit()
   

    
    
## 2. Extraire les URLs des dépôts logiciels dans les abstracts ou les fichiers PDF 

#pdfplumber : Utilisé pour extraire du texte à partir des fichiers PDF.
# io : Fournit des outils pour manipuler des fichiers en mémoire (ici, le PDF téléchargé).
# re : Module pour travailler avec des expressions régulières, utilisé pour extraire des URLs dans le texte.



# Connexion à la base de données SQLite
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor()

# Ajouter une colonne software_links pour stocker les liens de dépôt logiciel si elle n'existe pas
try:
    c.execute("ALTER TABLE articles ADD COLUMN software_links TEXT")
    database.commit()
except sqlite3.OperationalError:  # colonne existe déjà 
    pass  # La colonne existe déjà

# Fonction pour vérifier si un lien est valide
def is_valid_link(link):
    return link.startswith('http://') or link.startswith('https://')

# Fonction pour nettoyer les liens partiels ou incorrects
def clean_link(link):
    link = link.strip(').;,')  # Supprimer les parenthèses et les points en fin de lien
    return link if is_valid_link(link) else None

# Fonction pour extraire les liens à partir d'un texte
def extract_links_from_text(text):
    return re.findall(r'https?://\S+', text)


#fonction principale
# Fonction pour extraire les liens de dépôt logiciel
def extract_software_links():
    # Récupérer tous les articles de la base de données
    c.execute("SELECT id, title, pdf_link, abstract, software_links FROM articles")
    articles = c.fetchall() #récupère tous les articles 

    for article in articles:
        article_id, title, pdf_link, abstract, existing_links = article

        # Si l'article a déjà des liens de dépôt logiciel, on l'ignore
        if existing_links:
            print(f"Article {article_id} déjà traité, on passe au suivant.")
            continue

        software_links_set = set()  # Utiliser un set pour éliminer les doublons

            
            #extraire lien a partir du pdf
        # Vérifier le lien PDF
        if pdf_link and pdf_link != 'Lien PDF non disponible':
            try:
                # Télécharger le fichier PDF
                response = requests.get(pdf_link)
                response.raise_for_status()  # Vérifie si la requête a réussi

                # Utiliser pdfplumber pour extraire le texte du PDF
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            # Rechercher des liens de dépôt logiciel dans le texte
                            software_links_set.update(extract_links_from_text(text))

            except Exception as e:
                print(f"Erreur lors de l'ouverture du PDF pour l'article {article_id}: {e}")

        # Si aucun lien n'a été trouvé dans le PDF, vérifier l'abstract
        if not software_links_set and abstract != 'Abstract non disponible':
            software_links_set.update(extract_links_from_text(abstract))

        # Nettoyage des liens et validation
        valid_links = [clean_link(link) for link in software_links_set if clean_link(link)]
            #lien trouvés sont nettoyés et valide par clean_link() et is_valid_link().

        # Mise à jour de la base de données avec les liens de dépôt logiciel
        #liens valides trouvés, ajoutés à la base de données dans la colonne software_links 
        if valid_links:
            print(f"Liens de dépôt logiciel valides pour l'article {article_id} : {valid_links}")
            c.execute("UPDATE articles SET software_links = ? WHERE id = ?", (', '.join(valid_links), article_id))
        else:
            print(f"Aucun lien de dépôt logiciel trouvé pour l'article {article_id}")

        time.sleep(1)  # Pause pour éviter de surcharger le serveur

    # Sauvegarder les modifications dans la base de données
    database.commit()

# Appeler la fonction d'extraction
extract_software_links()

# Fermer la connexion à la base de données
#database.close()