# 🧪 GUIDE DE TEST - TABLETTES DE CHARGEMENT ET DÉCHARGEMENT

Ce guide vous explique comment tester le système de tablettes pour les opérateurs de chargement et de déchargement.

## 📋 PRÉREQUIS

1. **Lancer l'application Streamlit**
   ```bash
   streamlit run app.py
   ```

2. **Créer les comptes nécessaires** (si pas déjà fait) :
   - Un opérateur de chargement (avec une machine de type Excavatrice, Chargeuse, etc.)
   - Un opérateur de dumper (avec une machine de type Dumper, Camion, Benne)

---

## 🚀 MÉTHODE 1 : Deux Navigateurs Différents (Recommandé)

### Étape 1 : Préparer les comptes

1. **Connectez-vous en tant qu'ADMIN**
   - Créez un opérateur de chargement :
     - Nom : `Operateur_Chargement`
     - Rôle : `Operateur`
     - Machine assignée : Une Excavatrice ou Chargeuse
   
   - Créez un opérateur de dumper :
     - Nom : `Operateur_Dumper`
     - Rôle : `Operateur`
     - Machine assignée : Un Dumper ou Camion

2. **Créez les comptes utilisateurs** (ADMIN > Ajouter Utilisateur)
   - Utilisateur 1 : `chargeur` / mot de passe : `chargeur123`
   - Utilisateur 2 : `dumper` / mot de passe : `dumper123`

### Étape 2 : Ouvrir deux navigateurs

1. **Navigateur 1** (Chrome, Firefox, Edge, etc.)
   - Ouvrez : `http://localhost:8501`
   - Connectez-vous avec : `chargeur` / `chargeur123`
   - C'est votre **TABLETTE DE CHARGEMENT**

2. **Navigateur 2** (un autre navigateur ou mode navigation privée)
   - Ouvrez : `http://localhost:8501`
   - Connectez-vous avec : `dumper` / `dumper123`
   - C'est votre **TABLETTE DE DÉCHARGEMENT**

### Étape 3 : Tester le workflow

#### Sur la TABLETTE DE CHARGEMENT (Navigateur 1) :

1. Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
2. Dans la section **"📦 TABLETTE DE CHARGEMENT"** :
   - **Étape 1** : Sélectionnez l'opérateur dumper (`Operateur_Dumper`)
   - **Étape 2** : Cliquez sur un type de minerai (ex: 🥇 OR)
   - **Étape 3** : Cliquez sur un grade (ex: 🟢 HIGH GRADE)
   - **Étape 4** : Cliquez sur **"✅ VALIDER LE CHARGEMENT"**

#### Sur la TABLETTE DE DÉCHARGEMENT (Navigateur 2) :

1. Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
2. Vous devriez voir une notification dans la section **"🚀 CHARGEMENTS EN ATTENTE DE DÉMARRAGE"**
3. Cliquez sur **"✅ VALIDER DÉMARRAGE"**
4. Le chargement passe en **"📦 CHARGEMENTS EN COURS DE TRANSPORT"**
5. Cliquez sur **"✅ VALIDER DÉCHARGEMENT"**
6. Le système affiche :
   - ✅ Temps de cycle total
   - ⛽ Consommation carburant
   - 📍 Prochaine destination (pelle disponible)

---

## 🚀 MÉTHODE 2 : Mode Navigation Privée (Plus Simple)

### Étape 1 : Ouvrir deux fenêtres

1. **Fenêtre normale** : Connectez-vous avec `chargeur`
2. **Fenêtre navigation privée** (Ctrl+Shift+N sur Chrome) : Connectez-vous avec `dumper`

### Étape 2 : Tester le workflow

Suivez les mêmes étapes que la Méthode 1.

---

## 🚀 MÉTHODE 3 : Deux Onglets du Même Navigateur (Moins Recommandé)

⚠️ **Note** : Cette méthode peut causer des conflits de session. Utilisez-la seulement si les autres méthodes ne fonctionnent pas.

1. Ouvrez un onglet et connectez-vous avec `chargeur`
2. Ouvrez un nouvel onglet et connectez-vous avec `dumper`
3. Testez le workflow

---

## 📊 VÉRIFICATION DES RÉSULTATS

### Après validation du déchargement, vérifiez :

1. **Sur la tablette de déchargement** :
   - ✅ Message de succès : "Déchargement validé !"
   - ⏱️ Temps de cycle total affiché
   - ⛽ Consommation carburant affichée
   - 📍 Directive pour la prochaine pelle affichée

2. **Sur la tablette de chargement** :
   - 📬 Notification reçue : "Déchargement validé !"

3. **Dans les événements de cycle** :
   - Les événements sont enregistrés dans `st.session_state.cycle_events`
   - Vous pouvez les voir dans la section "SUIVI DES TEMPS DE CYCLE EN TEMPS RÉEL" (si vous êtes superviseur)

---

## 🔍 DÉPANNAGE

### Problème : Les notifications n'apparaissent pas

**Solution** :
- Vérifiez que les deux opérateurs sont bien connectés
- Rafraîchissez la page de la tablette de déchargement (F5)
- Vérifiez que l'opérateur dumper sélectionné correspond bien à celui connecté

### Problème : Aucune pelle disponible

**Solution** :
- Vérifiez qu'il y a des machines de type Excavatrice, Chargeuse, etc. dans la flotte
- Vérifiez que ces machines ont le statut "Active"
- Assurez-vous qu'elles ne sont pas toutes en train de charger

### Problème : L'opérateur dumper n'apparaît pas dans la liste

**Solution** :
- Vérifiez que l'opérateur a bien une machine de type Dumper, Camion ou Benne assignée
- Vérifiez dans RH > Assigner Machines que l'opérateur a bien une machine assignée

---

## 📝 CHECKLIST DE TEST COMPLET

- [ ] L'application Streamlit est lancée
- [ ] Deux comptes opérateurs sont créés (chargeur et dumper)
- [ ] Les machines sont assignées aux opérateurs
- [ ] Deux navigateurs/fenêtres sont ouverts avec les deux comptes
- [ ] Test de validation de chargement (chargeur)
- [ ] Test de validation de démarrage (dumper)
- [ ] Test de validation de déchargement (dumper)
- [ ] Vérification des calculs (temps de cycle, carburant)
- [ ] Vérification de la directive de prochaine pelle
- [ ] Vérification des notifications entre opérateurs

---

## 🎯 SCÉNARIO DE TEST COMPLET

1. **Chargeur** : Valide un chargement de 50T d'Or - High Grade pour Dumper_01
2. **Dumper** : Reçoit la notification et valide le démarrage
3. **Dumper** : Valide le déchargement à ROMPAD High Grade
4. **Système** : Affiche les métriques et la prochaine destination
5. **Chargeur** : Reçoit la notification de déchargement complet

---

## 💡 CONSEIL

Pour un test plus réaliste, vous pouvez :
- Ouvrir les deux tablettes côte à côte sur le même écran
- Simuler un délai entre les actions (attendre quelques secondes entre chaque étape)
- Tester avec différents types de minerais et grades
- Tester avec plusieurs cycles consécutifs

---

**Bon test ! 🚀**












