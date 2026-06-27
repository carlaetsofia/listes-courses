from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import secrets

app = Flask(__name__)
app.secret_key = "ma_cle_secrete_123"
import os
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "courses.db")
def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY,
        pseudo TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL,
        foyer_id INTEGER DEFAULT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS foyers (
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        nom TEXT,
        createur_id INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY,
        article TEXT NOT NULL,
        quantite TEXT DEFAULT '1',
        categorie TEXT DEFAULT 'Autre',
        coche INTEGER DEFAULT 0,
        utilisateur_id INTEGER,
        type_liste TEXT NOT NULL,
        foyer_id INTEGER DEFAULT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS historique (
        id INTEGER PRIMARY KEY,
        article TEXT NOT NULL,
        categorie TEXT,
        quantite TEXT,
        utilisateur_id INTEGER,
        type_liste TEXT,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS recettes (
        id INTEGER PRIMARY KEY,
        nom TEXT NOT NULL,
        utilisateur_id INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY,
        recette_id INTEGER,
        article TEXT NOT NULL,
        quantite TEXT DEFAULT '1',
        categorie TEXT DEFAULT 'Autre'
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS planning (
        id INTEGER PRIMARY KEY,
        jour TEXT NOT NULL,
        repas TEXT NOT NULL,
        recette_id INTEGER,
        utilisateur_id INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        contenu TEXT NOT NULL,
        utilisateur_id INTEGER,
        pseudo TEXT,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()



def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

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
            conn.execute("INSERT INTO utilisateurs (pseudo, mot_de_passe, email) VALUES (?, ?, ?)", (pseudo, mot_de_passe, email))
            conn.commit()
            conn.close()
            return redirect("/connexion")
        except Exception as e:
            return render_template("inscription.html", erreur=f"Erreur: {str(e)}")
    return render_template("inscription.html")

@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":
        pseudo = request.form.get("pseudo")
        mot_de_passe = hashlib.sha256(request.form.get("mot_de_passe").encode()).hexdigest()
        conn = get_db()
        user = conn.execute("SELECT * FROM utilisateurs WHERE pseudo=? AND mot_de_passe=?", (pseudo, mot_de_passe)).fetchone()
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
    if type_liste == "personnelle":
        courses = conn.execute(
            "SELECT * FROM courses WHERE utilisateur_id=? AND type_liste=? ORDER BY coche ASC, id ASC",
            (session["utilisateur_id"], "personnelle")
        ).fetchall()
    else:
        courses = conn.execute(
            "SELECT * FROM courses WHERE type_liste=? ORDER BY coche ASC, id ASC",
            ("commune",)
        ).fetchall()
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
        conn.execute(
            "INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (?, ?, ?, ?, ?)",
            (article, quantite, categorie, session["utilisateur_id"], type_liste)
        )
        conn.commit()
        conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/supprimer", methods=["POST"])
def supprimer(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    course_id = request.form.get("course_id")
    conn = get_db()
    conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
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
    conn.execute("UPDATE courses SET coche=? WHERE id=?", (nouveau_coche, course_id))
    conn.commit()
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
    conn.execute(
        "UPDATE courses SET quantite=?, categorie=? WHERE id=?",
        (quantite, categorie, course_id)
    )
    conn.commit()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/liste/<type_liste>/vider", methods=["POST"])
def vider(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    if type_liste == "personnelle":
        courses = conn.execute(
            "SELECT * FROM courses WHERE utilisateur_id=? AND type_liste=?",
            (session["utilisateur_id"], "personnelle")
        ).fetchall()
    else:
        courses = conn.execute(
            "SELECT * FROM courses WHERE type_liste=?",
            ("commune",)
        ).fetchall()
    for course in courses:
        conn.execute(
            "INSERT INTO historique (article, categorie, quantite, utilisateur_id, type_liste) VALUES (?, ?, ?, ?, ?)",
            (course["article"], course["categorie"], course["quantite"], session["utilisateur_id"], type_liste)
        )
    if type_liste == "personnelle":
        conn.execute("DELETE FROM courses WHERE utilisateur_id=? AND type_liste=?",
            (session["utilisateur_id"], "personnelle"))
    else:
        conn.execute("DELETE FROM courses WHERE type_liste=?", ("commune",))
    conn.commit()
    conn.close()
    return redirect("/liste/" + type_liste)

@app.route("/historique/<type_liste>")
def historique(type_liste):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    articles = conn.execute(
        "SELECT DISTINCT article, categorie, quantite FROM historique WHERE utilisateur_id=? AND type_liste=? ORDER BY date DESC LIMIT 50",
        (session["utilisateur_id"], type_liste)
    ).fetchall()
    conn.close()
    return render_template("historique.html", articles=articles, type_liste=type_liste)

@app.route("/recettes")
def recettes():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    recettes = conn.execute(
        "SELECT * FROM recettes WHERE utilisateur_id=?",
        (session["utilisateur_id"],)
    ).fetchall()
    conn.close()
    return render_template("recettes.html", recettes=recettes)

@app.route("/recettes/ajouter", methods=["POST"])
def ajouter_recette():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    nom = request.form.get("nom")
    if nom:
        conn = get_db()
        conn.execute(
            "INSERT INTO recettes (nom, utilisateur_id) VALUES (?, ?)",
            (nom, session["utilisateur_id"])
        )
        conn.commit()
        conn.close()
    return redirect("/recettes")

@app.route("/recettes/<int:recette_id>")
def recette_detail(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    recette = conn.execute("SELECT * FROM recettes WHERE id=?", (recette_id,)).fetchone()
    ingredients = conn.execute("SELECT * FROM ingredients WHERE recette_id=?", (recette_id,)).fetchall()
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
        conn.execute(
            "INSERT INTO ingredients (recette_id, article, quantite, categorie) VALUES (?, ?, ?, ?)",
            (recette_id, article, quantite, "Autre")
        )
        conn.commit()
        conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/recettes/<int:recette_id>/supprimer_ingredient", methods=["POST"])
def supprimer_ingredient(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    conn = get_db()
    conn.execute("DELETE FROM ingredients WHERE id=?", (ingredient_id,))
    conn.commit()
    conn.close()
    return redirect("/recettes/" + str(recette_id))

@app.route("/recettes/<int:recette_id>/supprimer", methods=["POST"])
def supprimer_recette(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    conn.execute("DELETE FROM ingredients WHERE recette_id=?", (recette_id,))
    conn.execute("DELETE FROM recettes WHERE id=?", (recette_id,))
    conn.commit()
    conn.close()
    return redirect("/recettes")

@app.route("/recettes/<int:recette_id>/ingredient_vers_liste", methods=["POST"])
def ingredient_vers_liste(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    type_liste = request.form.get("type_liste")
    conn = get_db()
    ingredient = conn.execute("SELECT * FROM ingredients WHERE id=?", (ingredient_id,)).fetchone()
    if ingredient:
        conn.execute(
            "INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (?, ?, ?, ?, ?)",
            (ingredient["article"], ingredient["quantite"], "Autre", session["utilisateur_id"], type_liste)
        )
        conn.commit()
    conn.close()
    return redirect("/recettes/" + str(recette_id))
@app.route("/recettes/<int:recette_id>/modifier_ingredient", methods=["POST"])
def modifier_ingredient(recette_id):
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    ingredient_id = request.form.get("ingredient_id")
    quantite = request.form.get("quantite") or "1"
    conn = get_db()
    conn.execute("UPDATE ingredients SET quantite=? WHERE id=?", (quantite, ingredient_id))
    conn.commit()
    conn.close()
    return redirect("/recettes/" + str(recette_id))
@app.route("/planning")
def planning():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    recettes = conn.execute(
        "SELECT * FROM recettes WHERE utilisateur_id=?",
        (session["utilisateur_id"],)
    ).fetchall()
    planning_db = conn.execute(
        "SELECT * FROM planning WHERE utilisateur_id=?",
        (session["utilisateur_id"],)
    ).fetchall()
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
    conn.execute(
        "DELETE FROM planning WHERE jour=? AND repas=? AND utilisateur_id=?",
        (jour, repas, session["utilisateur_id"])
    )
    if recette_id:
        conn.execute(
            "INSERT INTO planning (jour, repas, recette_id, utilisateur_id) VALUES (?, ?, ?, ?)",
            (jour, repas, recette_id, session["utilisateur_id"])
        )
    conn.commit()
    conn.close()
    return redirect("/planning")

@app.route("/planning/vers_liste", methods=["POST"])
def planning_vers_liste():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    type_liste = request.form.get("type_liste")
    conn = get_db()
    planning_db = conn.execute(
        "SELECT * FROM planning WHERE utilisateur_id=?",
        (session["utilisateur_id"],)
    ).fetchall()
    
    ingredients_cumules = {}
    for p in planning_db:
        if p["recette_id"]:
            ingredients = conn.execute(
                "SELECT * FROM ingredients WHERE recette_id=?",
                (p["recette_id"],)
            ).fetchall()
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
                    ingredients_cumules[cle] = {
                        "article": ingredient["article"],
                        "quantite": ingredient["quantite"],
                        "categorie": ingredient["categorie"]
                    }
    
    for ing in ingredients_cumules.values():
        conn.execute(
            "INSERT INTO courses (article, quantite, categorie, utilisateur_id, type_liste) VALUES (?, ?, ?, ?, ?)",
            (ing["article"], ing["quantite"], ing["categorie"], session["utilisateur_id"], type_liste)
        )
    conn.commit()
    conn.close()
    return redirect("/liste/" + type_liste)

    conn.commit()
    conn.close()
    return redirect("/liste/" + type_liste)
@app.route("/messages")
def messages():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    messages = conn.execute(
        "SELECT * FROM messages ORDER BY date ASC"
    ).fetchall()
    conn.close()
    return render_template("messages.html", messages=messages, utilisateur_id=session["utilisateur_id"])

@app.route("/messages/envoyer", methods=["POST"])
def envoyer_message():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    contenu = request.form.get("contenu")
    if contenu:
        conn = get_db()
        conn.execute(
            "INSERT INTO messages (contenu, utilisateur_id, pseudo) VALUES (?, ?, ?)",
            (contenu, session["utilisateur_id"], session["pseudo"])
        )
        conn.commit()
        conn.close()
    return redirect("/messages")
import random
import string

def generer_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route("/foyer")
def foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    user = conn.execute("SELECT * FROM utilisateurs WHERE id=?", (session["utilisateur_id"],)).fetchone()
    foyer = None
    membres = []
    if user["foyer_id"]:
        foyer = conn.execute("SELECT * FROM foyers WHERE id=?", (user["foyer_id"],)).fetchone()
        membres = conn.execute("SELECT * FROM utilisateurs WHERE foyer_id=?", (user["foyer_id"],)).fetchall()
    conn.close()
    return render_template("foyer.html", foyer=foyer, membres=membres)

@app.route("/foyer/creer", methods=["POST"])
def creer_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    code = generer_code()
    conn = get_db()
    conn.execute("INSERT INTO foyers (code, createur_id) VALUES (?, ?)", (code, session["utilisateur_id"]))
    foyer = conn.execute("SELECT * FROM foyers WHERE code=?", (code,)).fetchone()
    conn.execute("UPDATE utilisateurs SET foyer_id=? WHERE id=?", (foyer["id"], session["utilisateur_id"]))
    conn.commit()
    conn.close()
    return redirect("/foyer")

@app.route("/foyer/rejoindre", methods=["POST"])
def rejoindre_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    code = request.form.get("code").upper()
    conn = get_db()
    foyer = conn.execute("SELECT * FROM foyers WHERE code=?", (code,)).fetchone()
    if foyer:
        conn.execute("UPDATE utilisateurs SET foyer_id=? WHERE id=?", (foyer["id"], session["utilisateur_id"]))
        conn.commit()
        conn.close()
        return redirect("/foyer")
    conn.close()
    return render_template("foyer.html", foyer=None, membres=[], erreur="Code incorrect — vérifiez et réessayez !")

@app.route("/foyer/quitter", methods=["POST"])
def quitter_foyer():
    if "utilisateur_id" not in session:
        return redirect("/connexion")
    conn = get_db()
    conn.execute("UPDATE utilisateurs SET foyer_id=NULL WHERE id=?", (session["utilisateur_id"],))
    conn.commit()
    conn.close()
    return redirect("/foyer")
@app.route("/mot_de_passe_oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    if request.method == "POST":
        email = request.form.get("email")
        conn = get_db()
        user = conn.execute("SELECT * FROM utilisateurs WHERE email=?", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            conn.execute("UPDATE utilisateurs SET reset_token=? WHERE email=?", (token, email))
            conn.commit()
            lien = f"https://listes-courses.onrender.com/reinitialiser/{token}"
            message = Mail(
               
                from_email=os.environ.get("SENDGRID_FROM_EMAIL"),                to_emails=email,
                subject="Réinitialisation de votre mot de passe",
                html_content=f"<p>Cliquez sur ce lien pour réinitialiser votre mot de passe :</p><a href='{lien}'>{lien}</a>"
            )
            try:
                sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                sg.send(message)
            except Exception as e:
                print(e)
            conn.close()
            return render_template("mot_de_passe_oublie.html", message="Un email vous a été envoyé !")
        conn.close()
        return render_template("mot_de_passe_oublie.html", erreur="Aucun compte trouvé avec cet email !")
    return render_template("mot_de_passe_oublie.html")

@app.route("/reinitialiser/<token>", methods=["GET", "POST"])
def reinitialiser(token):
    conn = get_db()
    user = conn.execute("SELECT * FROM utilisateurs WHERE reset_token=?", (token,)).fetchone()
    if not user:
        conn.close()
        return redirect("/connexion")
    if request.method == "POST":
        mot_de_passe = request.form.get("mot_de_passe")
        mot_de_passe2 = request.form.get("mot_de_passe2")
        if mot_de_passe != mot_de_passe2:
            conn.close()
            return render_template("nouveau_mot_de_passe.html", erreur="Les mots de passe ne correspondent pas !")
        nouveau_mdp = hashlib.sha256(mot_de_passe.encode()).hexdigest()
        conn.execute("UPDATE utilisateurs SET mot_de_passe=?, reset_token=NULL WHERE reset_token=?", (nouveau_mdp, token))
        conn.commit()
        conn.close()
        return redirect("/connexion")
    conn.close()
    return render_template("nouveau_mot_de_passe.html")
@app.route("/reset-db-secret-123")
def reset_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
    id INTEGER PRIMARY KEY,
    pseudo TEXT UNIQUE NOT NULL,
    mot_de_passe TEXT NOT NULL,
    email TEXT DEFAULT NULL,
    reset_token TEXT DEFAULT NULL,
    foyer_id INTEGER DEFAULT NULL
)""")

if __name__ == "__main__":
    app.run(debug=True)