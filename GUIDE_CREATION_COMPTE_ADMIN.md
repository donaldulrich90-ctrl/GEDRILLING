# 👤 GUIDE DE CRÉATION DE COMPTE UTILISATEUR - ADMIN

## 📋 Règles de Création de Compte

### ✅ Invités
- Les comptes **Invité** peuvent être créés **librement** sans être enregistrés dans RH
- Pas de vérification RH nécessaire
- Nom d'utilisateur personnalisé

### ⚠️ Tous les Autres Rôles
- L'employé **DOIT être enregistré dans RH** avant de créer un compte
- Vous devez sélectionner l'employé depuis la liste RH
- Chaque employé ne peut avoir qu'**un seul compte**
- Le système détecte automatiquement si un employé a déjà un compte

---

## 🔄 Processus de Création de Compte

### Étape 1 : Enregistrer l'Employé dans RH (si ce n'est pas un Invité)

1. **Connectez-vous** en tant qu'Administrateur ou RH
2. Allez dans **RH > ➕ Ajouter Employé**
3. Remplissez les informations :
   - Nom Complet
   - **Rôle** : Operateur, Superviseur Production, etc.
   - Équipe, Shift, Date d'arrivée
4. Cliquez sur **"✅ ENREGISTRER L'EMPLOYÉ"**
5. Notez le **matricule** généré

---

### Étape 2 : Créer le Compte Utilisateur

1. Allez dans **ADMIN > ➕ Ajouter Utilisateur**

2. **Sélectionnez le Rôle** :
   - **Invite** : Pas besoin d'employé RH
   - **Autres rôles** : L'employé doit être dans RH

3. **Si le rôle n'est pas "Invite"** :
   - Une liste d'employés RH (du rôle sélectionné) s'affiche
   - **Seuls les employés sans compte** apparaissent dans la liste
   - Les employés ayant déjà un compte sont listés dans un expander en bas

4. **Sélectionnez l'Employé** :
   - Choisissez l'employé depuis la liste
   - Les informations de l'employé s'affichent automatiquement :
     - Nom
     - Matricule
     - Équipe
     - Shift

5. **Nom d'Utilisateur** :
   - Pour **Invite** : Saisissez manuellement
   - Pour **Autres** : Généré automatiquement à partir du nom (ex: "Jean Dupont" → "jean_dupont")
   - Vous pouvez modifier le nom d'utilisateur suggéré si nécessaire

6. **Mot de Passe** : Définissez un mot de passe sécurisé

7. **Permissions** (optionnel) :
   - Les permissions par défaut du rôle sont pré-sélectionnées
   - Vous pouvez personnaliser les permissions si nécessaire
   - Cochez "Utiliser les permissions personnalisées" pour activer

8. Cliquez sur **"✅ CRÉER L'UTILISATEUR"**

---

## 📊 Vérification des Comptes

### Dans RH > Liste Employés
- Une colonne **"Compte Utilisateur"** affiche :
  - ✅ `nom_utilisateur` si l'employé a un compte
  - ❌ Aucun compte si l'employé n'a pas de compte

### Dans ADMIN > Liste Utilisateurs
- Liste de tous les comptes utilisateurs créés

---

## ⚠️ Important

1. **Un employé = Un compte** :
   - Un employé ne peut avoir qu'un seul compte
   - Le système empêche la création de comptes multiples

2. **Ordre de création** :
   - **Pour les rôles autres qu'Invite** : Créer d'abord l'employé dans RH, puis le compte dans ADMIN
   - **Pour Invite** : Créer directement le compte dans ADMIN

3. **Détection automatique** :
   - Le système détecte automatiquement si un employé a déjà un compte
   - Les employés avec compte n'apparaissent pas dans la liste de sélection

---

## 📝 Exemple Complet

**Création d'un compte pour "Moussa Koné" (Opérateur)**

### Étape 1 : RH
1. RH > Ajouter Employé
   - Nom : "Moussa Koné"
   - Rôle : "Operateur"
   - Équipe : "A"
   - Shift : "3x8"
   - Date : 01/01/2024
   - Matricule généré : EMP-001

### Étape 2 : ADMIN
1. ADMIN > Ajouter Utilisateur
   - Rôle : "Operateur"
   - Sélectionner : "Moussa Koné (Matricule: EMP-001)"
   - Nom d'utilisateur : "moussa_kone" (généré automatiquement)
   - Mot de passe : `****`
   - Permissions : Par défaut (validation_operateur activé)
   - ✅ CRÉER L'UTILISATEUR

### Résultat
- Moussa Koné peut se connecter avec `moussa_kone`
- Il voit uniquement l'onglet "VALIDATION OPÉRATEUR"
- Si une machine de chargement est assignée, il voit l'interface de chargement
- Si une machine dumper est assignée, il voit l'interface de camion

---

## 🔍 Vérifications

### Pour Vérifier qu'un Employé a un Compte :
1. Allez dans **RH > Liste Employés**
2. Cherchez l'employé dans la liste
3. Consultez la colonne **"Compte Utilisateur"**
   - ✅ = A un compte
   - ❌ = Pas de compte

### Pour Créer un Compte Manquant :
1. Allez dans **ADMIN > Ajouter Utilisateur**
2. Sélectionnez le rôle
3. Sélectionnez l'employé dans la liste (s'il n'apparaît pas, il a déjà un compte)

---

**🎉 Le système garantit que chaque employé a au maximum un compte et que seuls les employés enregistrés dans RH peuvent avoir un compte (sauf Invités) !**














