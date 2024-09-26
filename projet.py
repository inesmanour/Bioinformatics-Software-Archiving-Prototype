'''Installation de biblio '''

#pip install beautifulsoup4
#pip install requests


import requests
from bs4 import BeautifulSoup
import sqlite3

''' 	Scraper les articles bioRxiv liés à la bioinformatique '''


url = 'https://www.biorxiv.org'

# requête récupére la page bioinfo
response = requests.get(f'{url}/collection/bioinformatics')
soup = BeautifulSoup(response.content, 'html.parser')

# creer base de données SQLite "bioinformatics_articles" 
conn = sqlite3.connect('bioinformatics_articles.db')
c = conn.cursor()

# create table 'articles' avec col id,title et le lien 
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT)''')
#id c'est un identifiant unique généré automatiquement 

# Requête pour récupérer la page bioinfo
response = requests.get(f'{url}/collection/bioinformatics')
soup = BeautifulSoup(response.content, 'html.parser')

# Trouver les liens vers les articles
articles = soup.find_all('a', class_='highwire-cite-linked-title')

'''	Vérifier chaque article, en cherchant des mots-clés liés à la bioinformatique dans le titre 
ou l’abstract et finir par afficher titre et lien de chaque article'''

# filtrer article
bioinfo_keywords = ['bioinformatics', 'genomics', 'proteomics', 'sequencing','chemistry', "structural", 'dynamic']
#trouver + de mots clé ines ! maybe struture , dynamique 

def contains_bioinfo_keywords(text):
    return any(keyword.lower() in text.lower() for keyword in bioinfo_keywords)

# Parcourir les articles et filtrer par mots-clés
for article in articles:
    title = article.text.strip()
    link = url + article['href']
    
    # Requête pour accéder à la page de l'article
    article_response = requests.get(link)
    article_soup = BeautifulSoup(article_response.content, 'html.parser')
    
    # Extraire l'abstract de l'article
    abstract = article_soup.find('div', class_='abstract').text if article_soup.find('div', class_='abstract') else ''
    
    # Vérifier si l'abstract ou le titre contient des mots-clés bioinformatiques
    if contains_bioinfo_keywords(title) or contains_bioinfo_keywords(abstract):
        print(f'Titre: {title}\nLien: {link}\n')
        
        # Insérer dans la base de données SQLite
        c.execute("INSERT INTO articles (title, link) VALUES (?, ?)", (title, link))
        
        
#si script trouve des articles pertinents, affiche titre et lien de la page 

# Sauvegarder (commit) les modifications dans la base de données
conn.commit()



''' Affichage de mes articles '''

# Requête pour récupérer tous les articles
c.execute("SELECT * FROM articles")

# recup et afficher les résultats 
rows = c.fetchall()
print("=== Liste des articles enregistrés ===\n")
for row in rows:
    print(f"ID: {row[0]}")
    print(f"Titre: {row[1]}")
    print(f"Lien: {row[2]}")
    print("-" * 50)  # séparateur visuel entre chaque article

# Fermer la connexion
conn.close()

print("Les titres et les liens des articles ont été enregistrés dans la base de données SQLite.")



''' note a moi meme '''
#plus de mots clés

#prochaine etape : 
#Étape 2 : Extraire les URLs des dépôts logiciels (dans les abstracts ou fichiers PDF).
#       Tu devras analyser les abstracts des articles pour détecter des liens vers des dépôts logiciels (par exemple GitHub, GitLab).
#       Si le lien n’est pas dans l’abstract, il peut parfois se trouver dans les fichiers PDF de l’article