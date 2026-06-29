from flask import Flask, render_template, request, redirect, session
import psycopg2
import psycopg2.extras
import hashlib
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import secrets
import os
import random
import string

app = Flask(__name__)
app.secret_key = "ma_cle_secrete_123"
app = Flask(__name__)
app.secret_key = "ma_cle_secrete_123"

from flask_babel import Babel, gettext as _
babel = Babel(app)
LANGUAGES = ['fr', 'en', 'es', 'de', 'pt', 'it']

def get_locale():
    return request.accept_languages.best_match(LANGUAGES)

babel = Babel(app, locale_selector=get_locale)


def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL non définie!")
    if not db_url.startswith("postgresql://"):
        db_url = "postgresql://" + db_url.split("://", 1)[-1]
    if "?" not in db_url:
        db_url += "?sslmode=require"
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
        id SERIAL PRIMARY KEY,
        pseudo TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL,
        email TEXT DEFAULT NULL,
        reset_token TEXT DEFAULT NULL,
        foyer_id INTEGER DEFAULT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS foyers (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        nom TEXT,
        createur_id INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        article TEXT NOT NULL,
        quantite TEXT DEFAULT '1',
        categorie TEXT DEFAULT 'Autre',
        coche INTEGER DEFAULT 0,
        utilisateur_id INTEGER,
        type_liste TEXT NOT NULL,
        foyer_id INTEGER DEFAULT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS historique (
        id SERIAL PRIMARY KEY,
        article TEXT NOT NULL,
        categorie TEXT,
        quantite TEXT,
        utilisateur_id INTEGER,
        type_liste TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS recettes (
        id SERIAL PRIMARY KEY,
        nom TEXT NOT NULL,
        utilisateur_id INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ingredients (
        id SERIAL PRIMARY KEY,
        recette_id INTEGER,
        article TEXT NOT NULL,
        quantite TEXT DEFAULT '1',
        categorie TEXT DEFAULT 'Autre'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS planning (
        id SERIAL PRIMARY KEY,
        jour TEXT NOT NULL,
        repas TEXT NOT NULL,
        recette_id INTEGER,
        utilisateur_id INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        contenu TEXT NOT NULL,
        utilisateur_id INTEGER,
        pseudo TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route("/")
def accueil():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    return render_template("accueil.html", pseudo=session["pseudo"])

@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if request.method == "POST":
        email = request.form.get("email")
        pseudo = request.form.get("pseudo")
        mot_de_passe = hashlib.sha256(request.form.get("mot_de_passe").encode()).hexdigest()
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO utilisateurs (pseudo, mot_de_passe, email) VALUES (%s, %s, %s)", (pseudo, mot_de_passe, email))
            conn.commit()
            cur.close()
            conn.close()
            return redirect("/connexion")
        except Exception as e:
            return render_template("inscription.html", erreur="Ce pseudo existe déjà !")
    return render_template("inscription.html")

@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        pseudo = request.form.get("pseudo")
        mot_de_passe = hashlib.sha256(request.form.get("mot_de_passe").encode()).hexdigest()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM utilisateurs WHERE pseudo=%s AND mot_de_passe=%s", (pseudo, mot_de_passe))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session["utilisateur_id"] = user["id"]
            session["pseudo"] = user["pseudo"]
            session["foyer_id"] = user["foyer_id"]
            return redirect("/")
        return render_template("connexion.html", erreur="Pseudo ou mot de passe incorrect !")
    return render_template("connexion.html")

@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect("/connexion")

@app.route("/liste/<type_liste>")
def liste(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    if type_liste == "personnelle":
        cur.execute("SELECT * FROM courses WHERE utilisateur_id=%s AND type_liste=%s ORDER BY coche ASC, id ASC", (session["utilisateur_id"], "personnelle"))
    else:
        cur.execute("SELECT * FROM courses WHERE type_liste=%s ORDER BY coche ASC, id ASC", ("commune",))
    courses = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("liste.html", courses=courses, type_liste=type_liste)

@app.route("/liste/<type_liste>/ajouter", methods=["POST"])
def ajouter(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    article = request.form.get("article")
    quantite = request.form.get("quantite") or "1"
    categorie = request.form.get("categorie") or "Autre"
    if article:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (%s, %s, %s, %s, %s)", (article, quantite, categorie, session["utilisateur_id"], type_liste))
        conn.commit()
        cur.close()
        conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/supprimer", methods=["POST"])
def supprimer(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    course_id = request.form.get("course_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/cocher", methods=["POST"])
def cocher(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    course_id = request.form.get("course_id")
    coche = request.form.get("coche")
    nouveau_coche = 0 if coche == "1" else 1
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE courses SET coche=%s WHERE id=%s", (nouveau_coche, course_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/modifier", methods=["POST"])
def modifier(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    course_id = request.form.get("course_id")
    quantite = request.form.get("quantite") or "1"
    categorie = request.form.get("categorie") or "Autre"
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE courses SET quantite=%s, categorie=%s WHERE id=%s", (quantite, categorie, course_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/vider", methods=["POST"])
def vider(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    if type_liste == "personnelle":
        cur.execute("SELECT * FROM courses WHERE utilisateur_id=%s AND type_liste=%s", (session["utilisateur_id"], "personnelle"))
    else:
        cur.execute("SELECT * FROM courses WHERE type_liste=%s", ("commune",))
    courses = cur.fetchall()
    for course in courses:
        cur.execute("INSERT INTO historique (article, categorie, quantite, utilisateur_id, type_liste) VALUES (%s, %s, %s, %s, %s)", (course["article"], course["categorie"], course["quantite"], session["utilisateur_id"], type_liste))
    if type_liste == "personnelle":
        cur.execute("DELETE FROM courses WHERE utilisateur_id=%s AND type_liste=%s", (session["utilisateur_id"], "personnelle"))
    else:
        cur.execute("DELETE FROM courses WHERE type_liste=%s", ("commune",))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/historique/<type_liste>")
def historique(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT article, categorie, quantite FROM historique WHERE utilisateur_id=%s AND type_liste=%s ORDER BY MAX(date) DESC LIMIT 50", (session["utilisateur_id"], type_liste))
    articles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("historique.html", articles=articles, type_liste=type_liste)

@app.route("/recettes")
def recettes():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recettes WHERE utilisateur_id=%s", (session["utilisateur_id"],))
    recettes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("recettes.html", recettes=recettes)

@app.route("/recettes/ajouter", methods=["POST"])
def ajouter_recette():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    nom = request.form.get("nom")
    if nom:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO recettes (nom, utilisateur_id) VALUES (%s, %s)", (nom, session["utilisateur_id"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect("/recettes")

@app.route("/recettes/<int:recette_id>")
def recette_detail(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recettes WHERE id=%s", (recette_id,))
    recette = cur.fetchone()
    cur.execute("SELECT * FROM ingredients WHERE recette_id=%s", (recette_id,))
    ingredients = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("recette_detail.html", recette=recette, ingredients=ingredients)

@app.route("/recettes/<int:recette_id>/ajouter_ingredient", methods=["POST"])
def ajouter_ingredient(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    article = request.form.get("article")
    quantite = request.form.get("quantite") or "1"
    if article:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO ingredients (recette_id, article, quantite, categorie) VALUES (%s, %s, %s, %s)", (recette_id, article, quantite, "Autre"))
        conn.commit()
        cur.close()
        conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/recettes/<int:recette_id>/supprimer_ingredient", methods=["POST"])
def supprimer_ingredient(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ingredients WHERE id=%s", (ingredient_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/recettes/<int:recette_id>/supprimer", methods=["POST"])
def supprimer_recette(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ingredients WHERE recette_id=%s", (recette_id,))
    cur.execute("DELETE FROM recettes WHERE id=%s", (recette_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/recettes")

@app.route("/recettes/<int:recette_id>/ingredient_vers_liste", methods=["POST"])
def ingredient_vers_liste(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    type_liste = request.form.get("type_liste")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ingredients WHERE id=%s", (ingredient_id,))
    ingredient = cur.fetchone()
    if ingredient:
        cur.execute("INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (%s, %s, %s, %s, %s)", (ingredient["article"], ingredient["quantite"], "Autre", session["utilisateur_id"], type_liste))
        conn.commit()
    cur.close()
    conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/recettes/<int:recette_id>/modifier_ingredient", methods=["POST"])
def modifier_ingredient(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    quantite = request.form.get("quantite") or "1"
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE ingredients SET quantite=%s WHERE id=%s", (quantite, ingredient_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/planning")
def planning():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recettes WHERE utilisateur_id=%s", (session["utilisateur_id"],))
    recettes = cur.fetchall()
    cur.execute("SELECT * FROM planning WHERE utilisateur_id=%s", (session["utilisateur_id"],))
    planning_db = cur.fetchall()
    cur.close()
    conn.close()
    planning = {p["jour"] + "_" + p["repas"]: p["recette_id"] for p in planning_db}
    return render_template("planning.html", recettes=recettes, planning=planning)

@app.route("/planning/sauvegarder", methods=["POST"])
def sauvegarder_planning():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    jour = request.form.get("jour")
    repas = request.form.get("repas")
    recette_id = request.form.get("recette_id") or None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM planning WHERE jour=%s AND repas=%s AND utilisateur_id=%s", (jour, repas, session["utilisateur_id"]))
    if recette_id:
        cur.execute("INSERT INTO planning (jour, repas, recette_id, utilisateur_id) VALUES (%s, %s, %s, %s)", (jour, repas, recette_id, session["utilisateur_id"]))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/planning")

@app.route("/planning/vers_liste", methods=["POST"])
def planning_vers_liste():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    type_liste = request.form.get("type_liste")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM planning WHERE utilisateur_id=%s", (session["utilisateur_id"],))
    planning_db = cur.fetchall()
    ingredients_cumules = {}
    for p in planning_db:
        if p["recette_id"]:
            cur.execute("SELECT * FROM ingredients WHERE recette_id=%s", (p["recette_id"],))
            ingredients = cur.fetchall()
            for ingredient in ingredients:
                cle = ingredient["article"].lower()
                if cle in ingredients_cumules:
                    try:
                        qte_existante = float(ingredients_cumules[cle]["quantite"])
                        qte_nouvelle = float(ingredient["quantite"])
                        ingredients_cumules[cle]["quantite"] = str(int(qte_existante + qte_nouvelle))
                    except:
                        pass
                else:
                    ingredients_cumules[cle] = {"article": ingredient["article"], "quantite": ingredient["quantite"], "categorie": ingredient["categorie"]}
    for ing in ingredients_cumules.values():
        cur.execute("INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (%s, %s, %s, %s, %s)", (ing["article"], ing["quantite"], ing["categorie"], session["utilisateur_id"], type_liste))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/messages")
def messages():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages ORDER BY date ASC")
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("messages.html", messages=messages, utilisateur_id=session["utilisateur_id"])

@app.route("/messages/envoyer", methods=["POST"])
def envoyer_message():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    contenu = request.form.get("contenu")
    if contenu:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (contenu, utilisateur_id, pseudo) VALUES (%s, %s, %s)", (contenu, session["utilisateur_id"], session["pseudo"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect("/messages")

def generer_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route("/foyer")
def foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM utilisateurs WHERE id=%s", (session["utilisateur_id"],))
    user = cur.fetchone()
    foyer = None
    membres = []
    if user["foyer_id"]:
        cur.execute("SELECT * FROM foyers WHERE id=%s", (user["foyer_id"],))
        foyer = cur.fetchone()
        cur.execute("SELECT * FROM utilisateurs WHERE foyer_id=%s", (user["foyer_id"],))
        membres = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("foyer.html", foyer=foyer, membres=membres)

@app.route("/foyer/creer", methods=["POST"])
def creer_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    code = generer_code()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO foyers (code, createur_id) VALUES (%s, %s) RETURNING id", (code, session["utilisateur_id"]))
    foyer_id = cur.fetchone()["id"]
    cur.execute("UPDATE utilisateurs SET foyer_id=%s WHERE id=%s", (foyer_id, session["utilisateur_id"]))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/foyer")

@app.route("/foyer/rejoindre", methods=["POST"])
def rejoindre_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    code = request.form.get("code").upper()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM foyers WHERE code=%s", (code,))
    foyer = cur.fetchone()
    if foyer:
        cur.execute("UPDATE utilisateurs SET foyer_id=%s WHERE id=%s", (foyer["id"], session["utilisateur_id"]))
        conn.commit()
        cur.close()
        conn.close()
        return redirect("/foyer")
    cur.close()
    conn.close()
    return render_template("foyer.html", foyer=None, membres=[], erreur="Code incorrect — vérifiez et réessayez !")

@app.route("/foyer/quitter", methods=["POST"])
def quitter_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE utilisateurs SET foyer_id=NULL WHERE id=%s", (session["utilisateur_id"],))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/foyer")

@app.route("/mot_de_passe_oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    if request.method == "POST":
        email = request.form.get("email")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM utilisateurs WHERE email=%s", (email,))
        user = cur.fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            cur.execute("UPDATE utilisateurs SET reset_token=%s WHERE email=%s", (token, email))
            conn.commit()
            lien = f"https://listes-courses.onrender.com/reinitialiser/{token}"
            message = Mail(
                from_email=os.environ.get("SENDGRID_FROM_EMAIL"),
                to_emails=email,
                subject="Réinitialisation de votre mot de passe",
                html_content=f"<p>Cliquez sur ce lien pour réinitialiser votre mot de passe :</p><a href='{lien}'>{lien}</a>"
            )
            try:
                sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                sg.send(message)
            except Exception as e:
                print(e)
            cur.close()
            conn.close()
            return render_template("mot_de_passe_oublie.html", message="Un email vous a été envoyé !")
        cur.close()
        conn.close()
        return render_template("mot_de_passe_oublie.html", erreur="Aucun compte trouvé avec cet email !")
    return render_template("mot_de_passe_oublie.html")

@app.route("/reinitialiser/<token>", methods=["GET", "POST"])
def reinitialiser(token):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM utilisateurs WHERE reset_token=%s", (token,))
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        return redirect("/connexion")
    if request.method == "POST":
        mot_de_passe = request.form.get("mot_de_passe")
        mot_de_passe2 = request.form.get("mot_de_passe2")
        if mot_de_passe != mot_de_passe2:
            cur.close()
            conn.close()
            return render_template("nouveau_mot_de_passe.html", erreur="Les mots de passe ne correspondent pas !")
        nouveau_mdp = hashlib.sha256(mot_de_passe.encode()).hexdigest()
        cur.execute("UPDATE utilisateurs SET mot_de_passe=%s, reset_token=NULL WHERE reset_token=%s", (nouveau_mdp, token))
        conn.commit()
        cur.close()
        conn.close()
        return redirect("/connexion")
    cur.close()
    conn.close()
    return render_template("nouveau_mot_de_passe.html")

if __name__ == "__main__":
    app.run(debug=True)