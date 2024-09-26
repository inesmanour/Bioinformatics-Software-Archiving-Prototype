'''Installation de biblio '''

#pip install beautifulsoup4
#pip install requests


import requests
from bs4 import BeautifulSoup
import sqlite3

''' 	Scraper les articles bioRxiv liés à la bioinformatique '''

url = 'https://www.biorxiv.org'

# requête récupére la page bioinfo
response = requests.get(url + '/collection/bioinformatics')
soup = BeautifulSoup(response.content, 'html.parser') #convertit le html et analyse 
                                                       #.content ->renvoie code htm sous forme de bytes  
# creer base de données SQLite "bioinformatics_articles" 
database = sqlite3.connect('bioinformatics_articles.db')
c = database.cursor() #ici le curseur 'c' permettra d'executer/parcourir les requetes SQL sur database

# create table 'articles' avec col id,title et le lien 
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT)''')
#id c'est un identifiant unique généré automatiquement 


# Requête pour récupérer la page bioinfo
response = requests.get(f'{url}/collection/bioinformatics')
soup = BeautifulSoup(response.content, 'html.parser')

# Trouver les liens vers les articles via beautifulsoup
articles = soup.find_all('a', class_='highwire-cite-linked-title')#find liens hypertextes avec classe CSS

'''	Parcourir les articles et enregistrer leurs titres et liens''

# Parcourir tous les articles et enregistrer leurs titres et liens
for article in articles:
    title = article.text.strip() # extraire le titre dans la balise <a>, accessible via .text.
    link = url + article['href'] #extraire le lien , href=destination du lien de mon article
    
    # Afficher le titre et le lien de chaque article
    print(f'Titre: {title}\nLien: {link}\n')
    
    # Insérer dans la base de données SQLite
    c.execute("INSERT INTO articles (title, link) VALUES (?, ?)", (title, link))

 
# Sauvegarder (commit) les modifications dans la base de données
conn.commit()



''' Affichage de mes articles  dans la base de données'''
# affiche articles stockés dans database
c.execute("SELECT * FROM articles")

rows = c.fetchall() #récupere tous les results de la requete d'avant =tuple(id,title,link) de chaque article

print("=== Liste des articles enregistrés ===\n")

for row in rows:
    print(f"ID: {row[0]}")
    print(f"Titre: {row[1]}")
    print(f"Lien: {row[2]}")
    print("-" * 50)  # separateur visuel entre chaque article

# Fermer la connexion à la base de données
conn.close()

print("Les titres et les liens des articles ont été enregistrés dans la base de données SQLite.")


''' note a moi meme '''

#prochaine etape : 
#Étape 2 : Extraire les URLs des dépôts logiciels (dans les abstracts ou fichiers PDF).
#       Tu devras analyser les abstracts des articles pour détecter des liens vers des dépôts logiciels (par exemple GitHub, GitLab).
#       Si le lien n’est pas dans l’abstract, il peut parfois se trouver dans les fichiers PDF de l’article
