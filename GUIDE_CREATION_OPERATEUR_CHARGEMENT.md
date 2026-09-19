# 🚛 GUIDE DE CRÉATION D'UN COMPTE OPÉRATEUR DE CHARGEMENT

## 📋 Étapes pour Créer un Opérateur de Chargement

### Étape 1 : Créer le Compte Utilisateur

1. **Connectez-vous** en tant qu'**Administrateur** ou avec un compte ayant les permissions **ADMIN**

2. Allez dans l'onglet **ADMIN** (ou **GESTION UTILISATEURS**)

3. Cliquez sur l'onglet **"➕ Ajouter Utilisateur"**

4. Remplissez le formulaire :
   - **Nom d'utilisateur** : ex: `jean_chargeur` ou `pelle_01`
   - **Mot de passe** : définissez un mot de passe sécurisé
   - **Rôle** : Sélectionnez **"Operateur"**

5. Cliquez sur **"✅ CRÉER L'UTILISATEUR"**

6. Notez le **nom d'utilisateur** créé, vous en aurez besoin à l'étape 3.

---

### Étape 2 : Créer l'Employé dans RH

1. Allez dans l'onglet **RH**

2. Cliquez sur l'onglet **"➕ Ajouter Employé"**

3. Remplissez le formulaire :
   - **Nom Complet** : Le nom de l'opérateur (ex: "Jean Dupont")
   - **Rôle** : Sélectionnez **"Operateur"**
   - **Équipe** : Sélectionnez l'équipe (A, B, ou C)
   - **Type de Shift** : Sélectionnez le shift (3x8, Standard, Jour, Nuit)
   - **Date d'Arrivée** : Date d'arrivée de l'employé

4. Cliquez sur **"✅ ENREGISTRER L'EMPLOYÉ"**

5. **Notez le matricule** généré automatiquement (ex: EMP-001)

---

### Étape 3 : Assigner une Machine de Chargement

1. Toujours dans l'onglet **RH**, cliquez sur l'onglet **"🚛 Assigner Machines"**

2. Dans le formulaire :
   - **Sélectionner l'Opérateur** : Choisissez le nom de l'employé créé à l'étape 2
   - **Sélectionner la Machine** : Choisissez une machine de type :
     - **Pelle** (ex: EX-01, EX-02) 🚜
     - **Chargeuse** (ex: WL-01, WL-02) 🚛
     - **Excavatrice** (ex: EX-03, EX-04) 🚜

3. Cliquez sur **"✅ ASSIGNER LA MACHINE"**

4. Vous verrez un message de confirmation : **"Cet opérateur est maintenant un Opérateur de Chargement 🚛"**

---

### Étape 4 : Vérifier l'Assignation

1. Dans l'onglet **"🚛 Assigner Machines"**, vous verrez en bas :
   - **Liste des Assignations Actuelles**
   - Le nom de l'opérateur
   - La machine assignée
   - **Type Opérateur** : "Opérateur de Chargement 🚛"

---

## ✅ Résultat Final

Après ces 4 étapes, l'opérateur pourra :

1. **Se connecter** avec le nom d'utilisateur créé à l'étape 1
2. **Voir uniquement** l'onglet **"VALIDATION OPÉRATEUR"**
3. **Utiliser l'interface de chargement** avec :
   - Sélection du camion
   - Sélection du type de minerai
   - Validation de fin de chargement
   - Donner le top départ au camion

---

## 🔄 Différence entre Opérateur de Chargement et Opérateur de Camion

| Type | Machine Assignée | Interface |
|------|-----------------|-----------|
| **Opérateur de Chargement** 🚛 | Pelle, Chargeuse, Excavatrice | Interface de chargement (sélection camion, type minerai, top départ) |
| **Opérateur de Camion** 🚚 | Dumper (DT-01, DT-02, etc.) | Interface camion (accepter transport, valider déchargement) |

---

## ❓ Questions Fréquentes

### Q: Comment savoir si un opérateur est bien un opérateur de chargement ?
**R:** Dans l'onglet **RH > Assigner Machines**, la colonne "Type Opérateur" affiche "Opérateur de Chargement 🚛"

### Q: Que faire si j'ai assigné la mauvaise machine ?
**R:** Retournez dans **RH > Assigner Machines**, sélectionnez l'opérateur, puis sélectionnez la bonne machine et validez.

### Q: Un opérateur peut-il être à la fois chargeur et camion ?
**R:** Non, un opérateur ne peut avoir qu'**une seule machine assignée** à la fois. Il faut créer deux comptes séparés.

### Q: Comment créer un opérateur de camion ?
**R:** Suivez les mêmes étapes, mais à l'**Étape 3**, assignez une machine de type **Dumper** (ex: DT-01, DT-02).

---

## 📝 Exemple Complet

**Création de "Moussa Koné" comme Opérateur de Chargement :**

1. **ADMIN > Ajouter Utilisateur**
   - Nom d'utilisateur: `moussa_kone`
   - Mot de passe: `****`
   - Rôle: `Operateur`

2. **RH > Ajouter Employé**
   - Nom: `Moussa Koné`
   - Rôle: `Operateur`
   - Équipe: `A`
   - Shift: `3x8`
   - Date: `01/01/2024`

3. **RH > Assigner Machines**
   - Opérateur: `Moussa Koné`
   - Machine: `EX-01` (Pelle)

4. **Résultat** : Moussa Koné peut se connecter avec `moussa_kone` et utiliser l'interface de chargement !

---

**🎉 Félicitations ! Vous avez créé un opérateur de chargement !**














