# 📱 GUIDE DE TEST - SYSTÈME DE NOTIFICATION OPÉRATEUR

## 🚀 DÉMARRAGE DE L'APPLICATION

### 1. Lancer l'application Streamlit

```bash
streamlit run app.py
```

L'application s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

---

## 👤 CONNEXION EN TANT QU'OPÉRATEUR

### Option 1 : Utiliser un compte opérateur existant
- **Nom d'utilisateur** : Un des opérateurs existants (ex: "Moussa Koné", "Jean Ouedraogo")
- **Mot de passe** : Le mot de passe défini pour cet opérateur

### Option 2 : Créer un nouvel opérateur (en tant qu'Administrateur)
1. Connectez-vous en tant qu'**Administrateur**
2. Allez dans l'onglet **ADMIN**
3. Créez un nouvel utilisateur avec le rôle **"Operateur"**
4. Déconnectez-vous et reconnectez-vous avec ce nouvel opérateur

---

## 🧪 SCÉNARIOS DE TEST

### 📋 TEST 1 : VALIDATION DE CHARGEMENT (Opérateur de Chargement)

**Objectif** : Tester le système de notification de chargement avec type de minerai

**Étapes** :
1. Connectez-vous en tant qu'**Opérateur** (ex: "Moussa Koné")
2. Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
3. Dans la section **"🚛 VALIDATION DE CHARGEMENT"** :
   - Sélectionnez une machine de chargement
   - Choisissez un type de minerai (ex: "Or")
   - Entrez une quantité (ex: 50 tonnes)
   - Sélectionnez la destination (ex: "ROMPAD")
   - Ajoutez un commentaire si nécessaire
   - Cliquez sur **"✅ VALIDER LE CHARGEMENT"**

**Résultat attendu** :
- ✅ Message de succès : "Chargement validé ! X T de [Type] notifiés aux opérateurs de dumper."
- ✅ Une notification apparaît dans la section "🔔 NOTIFICATIONS EN TEMPS RÉEL"
- ✅ Le chargement apparaît dans la section "🚚 RÉCEPTION DE CHARGEMENT" pour les autres opérateurs

---

### 📋 TEST 2 : RÉCEPTION DE CHARGEMENT (Opérateur de Dumper)

**Objectif** : Tester la réception et l'acceptation d'un chargement

**Étapes** :
1. **Dans un autre navigateur ou onglet** (pour simuler un autre opérateur) :
   - Connectez-vous avec un **autre opérateur** (ex: "Jean Ouedraogo")
   - Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
   
2. Dans la section **"🚚 RÉCEPTION DE CHARGEMENT"** :
   - Vous devriez voir le chargement créé dans le TEST 1
   - Cliquez sur l'expandeur pour voir les détails
   - Cliquez sur **"✅ Accepter et Aller vers [Destination]"**

**Résultat attendu** :
- ✅ Message de succès : "Transport accepté ! Déplacez-vous vers [Destination]."
- ✅ Le statut du chargement passe à "En transport"
- ✅ Une notification est envoyée à l'opérateur de chargement
- ✅ Un événement de cycle est enregistré pour le calcul du temps de cycle

---

### 📋 TEST 3 : SUIVI DES TEMPS DE CYCLE

**Objectif** : Vérifier le calcul automatique des temps de cycle

**Étapes** :
1. Après avoir effectué le TEST 1 et TEST 2, allez dans la section **"⏱️ SUIVI DES TEMPS DE CYCLE EN TEMPS RÉEL"**
2. Vérifiez que :
   - Les cycles sont affichés dans un tableau
   - Les temps de cycle sont calculés (en minutes)
   - Les statistiques (moyen, min, max) sont affichées

**Résultat attendu** :
- ✅ Tableau avec les cycles complets (chargement → transport)
- ✅ Temps de cycle calculé automatiquement
- ✅ Statistiques affichées (moyen, min, max)

---

### 📋 TEST 4 : SIGNALEMENT DE PANNE

**Objectif** : Tester le système de signalement de pannes

**Étapes** :
1. Dans l'onglet **"VALIDATION OPÉRATEUR"**
2. Dans la section **"🚨 SIGNALEMENT DE PANNES"** :
   - Sélectionnez une machine
   - Choisissez un type de panne (ex: "Mécanique")
   - Sélectionnez la gravité (ex: "Majeure")
   - Décrivez la panne
   - Cochez "Machine Arrêtée" si nécessaire
   - Cochez "Besoin d'Assistance Immédiate" si urgent
   - Cliquez sur **"🚨 SIGNALER LA PANNE"**

**Résultat attendu** :
- ✅ Message d'erreur (rouge) : "Panne signalée ! Les superviseurs et mécaniciens ont été notifiés."
- ✅ Une notification apparaît dans la section notifications
- ✅ Les superviseurs et mécaniciens reçoivent une notification

---

### 📋 TEST 5 : SIGNALEMENT D'ARRÊT

**Objectif** : Tester le signalement d'arrêts de machine

**Étapes** :
1. Dans la section **"⏸️ SIGNALEMENT D'ARRÊTS"** :
   - Sélectionnez une machine
   - Choisissez un type d'arrêt (ex: "Pause")
   - Entrez une durée estimée (ex: 15 minutes)
   - Ajoutez une raison
   - Cliquez sur **"⏸️ SIGNALER L'ARRÊT"**

**Résultat attendu** :
- ✅ Message d'avertissement : "Arrêt signalé pour [Machine]."
- ✅ L'événement est enregistré dans les événements de cycle

---

### 📋 TEST 6 : NOTIFICATIONS EN TEMPS RÉEL

**Objectif** : Vérifier l'affichage des notifications

**Étapes** :
1. Effectuez plusieurs actions (chargement, panne, arrêt)
2. Vérifiez la section **"🔔 NOTIFICATIONS EN TEMPS RÉEL"**
3. Les notifications devraient apparaître avec :
   - Type de notification (chargement, panne, cycle)
   - Opérateur émetteur
   - Message
   - Timestamp

**Résultat attendu** :
- ✅ Les notifications s'affichent en temps réel
- ✅ Différentes couleurs selon le type (vert=chargement, rouge=panne, bleu=cycle)
- ✅ Les 10 dernières notifications sont affichées

---

### 📋 TEST 7 : VALIDATION DES HEURES DE TRAVAIL

**Objectif** : Tester la validation des heures de travail

**Étapes** :
1. Dans la section **"⏰ VALIDATION DES HEURES DE TRAVAIL"** :
   - Sélectionnez une date
   - Entrez l'heure de début (ex: 08:00)
   - Entrez l'heure de fin (ex: 17:00)
   - Le système calcule automatiquement les heures travaillées
   - Entrez la durée de pause (ex: 60 minutes)
   - Cochez la confirmation
   - Signez avec votre nom
   - Cliquez sur **"✅ VALIDER LES HEURES"**

**Résultat attendu** :
- ✅ Message de succès : "Heures de travail validées avec succès"
- ✅ Les heures sont enregistrées dans l'historique

---

### 📋 TEST 8 : HISTORIQUE DES VALIDATIONS

**Objectif** : Vérifier l'historique et les statistiques

**Étapes** :
1. Allez dans la section **"📜 HISTORIQUE DES VALIDATIONS"**
2. Filtrez par type (Cycles, Production, Heures)
3. Vérifiez les statistiques affichées
4. Testez l'export CSV

**Résultat attendu** :
- ✅ Tableau avec toutes les validations
- ✅ Filtrage par type fonctionnel
- ✅ Statistiques calculées (total, production totale, heures totales)
- ✅ Export CSV fonctionnel

---

## 🔄 TEST AVEC PLUSIEURS OPÉRATEURS

Pour tester les notifications entre opérateurs :

1. **Ouvrez deux navigateurs différents** (ou deux onglets en mode navigation privée)
2. **Navigateur 1** : Connectez-vous avec "Moussa Koné" (Opérateur de Chargement)
3. **Navigateur 2** : Connectez-vous avec "Jean Ouedraogo" (Opérateur de Dumper)
4. Dans le **Navigateur 1** : Validez un chargement
5. Dans le **Navigateur 2** : Vérifiez que la notification apparaît
6. Dans le **Navigateur 2** : Acceptez le transport
7. Dans le **Navigateur 1** : Vérifiez que la notification de transport apparaît

---

## 🐛 DÉPANNAGE

### Problème : Les notifications n'apparaissent pas
- **Solution** : Vérifiez que vous êtes connecté en tant qu'opérateur
- **Solution** : Rafraîchissez la page (F5)

### Problème : Les temps de cycle ne se calculent pas
- **Solution** : Assurez-vous d'avoir effectué un chargement ET un transport
- **Solution** : Vérifiez que les deux opérateurs sont différents

### Problème : L'application ne démarre pas
- **Solution** : Vérifiez que Streamlit est installé : `pip install streamlit`
- **Solution** : Vérifiez que toutes les dépendances sont installées

---

## 📊 DONNÉES DE TEST RECOMMANDÉES

Pour tester efficacement, utilisez ces données :

- **Opérateur 1** : Moussa Koné (Chargement)
- **Opérateur 2** : Jean Ouedraogo (Dumper)
- **Machine** : N'importe quelle machine assignée à l'opérateur
- **Type de minerai** : Or
- **Quantité** : 50 tonnes
- **Destination** : ROMPAD

---

## ✅ CHECKLIST DE TEST COMPLÈTE

- [ ] Validation de chargement fonctionne
- [ ] Notifications envoyées aux opérateurs de dumper
- [ ] Réception de chargement fonctionne
- [ ] Acceptation de transport fonctionne
- [ ] Temps de cycle calculé automatiquement
- [ ] Signalement de panne fonctionne
- [ ] Notifications de panne envoyées aux superviseurs
- [ ] Signalement d'arrêt fonctionne
- [ ] Validation des heures fonctionne
- [ ] Historique des validations fonctionne
- [ ] Export CSV fonctionne
- [ ] Notifications en temps réel s'affichent
- [ ] Statistiques calculées correctement

---

## 🎯 PROCHAINES ÉTAPES

Une fois les tests effectués, vous pouvez :
1. Former les opérateurs à l'utilisation du système
2. Configurer les tablettes dans les cabines
3. Personnaliser les types de minerais selon vos besoins
4. Ajouter d'autres destinations si nécessaire

---

**Bon test ! 🚀**














