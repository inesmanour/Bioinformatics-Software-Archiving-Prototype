import requests
from bs4 import BeautifulSoup
import sqlite3
import time

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
             doi TEXT,
             date TEXT,
             pdf_link TEXT)''')
#id c'est un identifiant unique généré automatiquement 


'''parcourir les articles de la collection bio info contenant 2153 pages et enregistrer ces informations'''

# Nombre de pages à scraper (2153 au total but bcp de temps teste sur 5 page fait envirosn 8min)
total_pages = 2

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

        # extraire la date de publication (dans une balise meta ou time)
        date_tag = article_soup.find('meta', {'name': 'citation_publication_date'})
        date = date_tag['content'] if date_tag else 'Date non disponible'

        # extraire le lien vers le fichier PDF
        pdf_tag = article_soup.find('a', string='Download PDF')
        pdf_link = url + pdf_tag['href'] if pdf_tag else 'Lien PDF non disponible'

        # tout inserer dans la base de données SQLite
        c.execute(
            "INSERT INTO articles (title, link, doi, date, pdf_link) VALUES (?, ?, ?, ?, ?)",
            (title, link, doi, date, pdf_link)
        )

        # Afficher les informations extraites
        print(f'Titre: {title}\nLien: {link}\nDOI: {doi}\nDate de publication: {date}\nLien PDF: {pdf_link}\n')

        # pause d'une seconde pour éviter de surcharger le serveur
        time.sleep(1)
        
    # Sauvegarder les modifications dans la base de données après chaque page
    database.commit()
    
    
    
'''   Affichage de mes articles dans la base de données'''


# affiche articles stockés dans database
c.execute("SELECT * FROM articles")

rows = c.fetchall() #récupere tous les results de la requete d'avant =tuple(id,title,link) de chaque article

print("=== Liste des articles enregistrés ===\n")

for row in rows:
    print(f"ID: {row[0]}")
    print(f"Titre: {row[1]}")
    print(f"Lien: {row[2]}")
    print(f"DOI: {row[3]}")
    print(f"Date: {row[4]}")
    print(f"Lien PDF: {row[5]}")
    print("-" * 50)  # separateur visuel entre chaque article



print("Les titres et les liens des articles ont été enregistrés et affichés dans la base de données SQLite.")


# Fermer la connexion à la base de données (quand tu as finis)
#database.close() 

