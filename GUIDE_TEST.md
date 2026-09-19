# 🧪 GUIDE DE TEST - SYSTÈME DE NOTIFICATIONS OPÉRATEURS

## 📋 Prérequis
- Python installé
- Streamlit installé (`pip install streamlit`)
- Navigateur web

---

## 🚀 DÉMARRAGE DE L'APPLICATION

### 1. Démarrer Streamlit
```bash
streamlit run app.py
```

L'application s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

---

## 🔐 ÉTAPES DE TEST

### **TEST 1 : Se connecter comme Opérateur de Chargement**

1. **Identifiez-vous** :
   - Utilisez un compte existant ou créez-en un avec le rôle "Operateur"
   - Exemple : `username: op_chargeur` / `password: test123` / `role: Operateur`

2. **Accédez à l'onglet "VALIDATION OPÉRATEUR"**

3. **Test de Validation de Chargement** :
   - Allez dans la section "🚛 VALIDATION DE CHARGEMENT"
   - Sélectionnez une machine de chargement
   - Choisissez le type de minerai (ex: "Or")
   - Entrez une quantité (ex: 50 tonnes)
   - Sélectionnez la destination (ex: "ROMPAD")
   - Cliquez sur "✅ VALIDER LE CHARGEMENT"
   
   **Résultat attendu** : 
   - Message de succès
   - Notification envoyée aux opérateurs de dumper

---

### **TEST 2 : Se connecter comme Opérateur de Dumper**

1. **Ouvrez un deuxième onglet/navigateur** (ou une fenêtre privée)
   - Connectez-vous avec un autre compte opérateur
   - Exemple : `username: op_dumper` / `password: test123` / `role: Operateur`

2. **Accédez à l'onglet "VALIDATION OPÉRATEUR"**

3. **Test de Réception de Chargement** :
   - Vérifiez la section "🔔 NOTIFICATIONS EN TEMPS RÉEL"
   - Vous devriez voir la notification du chargement
   - Allez dans "🚚 RÉCEPTION DE CHARGEMENT"
   - Vous devriez voir le chargement disponible dans la liste
   - Cliquez sur "✅ Accepter et Aller vers ROMPAD"
   
   **Résultat attendu** :
   - Le statut du chargement passe à "En transport"
   - Notification envoyée à l'opérateur de chargement
   - Événement enregistré pour le calcul du temps de cycle

---

### **TEST 3 : Test du Calcul du Temps de Cycle**

1. **Retournez sur l'onglet de l'opérateur de chargement**
   - Allez dans la section "⏱️ SUIVI DES TEMPS DE CYCLE EN TEMPS RÉEL"
   - Vous devriez voir le cycle calculé avec :
     - Opérateur de chargement
     - Opérateur de transport
     - Temps de cycle en minutes
     - Statistiques (moyen, min, max)

---

### **TEST 4 : Test de Signalement de Panne**

1. **Connectez-vous comme opérateur**

2. **Allez dans "🚨 SIGNALEMENT DE PANNES"** :
   - Sélectionnez une machine
   - Choisissez le type de panne (ex: "Mécanique")
   - Sélectionnez la gravité (ex: "Majeure")
   - Décrivez la panne
   - Cochez "Machine Arrêtée" si nécessaire
   - Cliquez sur "🚨 SIGNALER LA PANNE"
   
   **Résultat attendu** :
   - Panne enregistrée
   - Notifications envoyées aux superviseurs et mécaniciens

3. **Connectez-vous comme Superviseur ou Mécanicien** :
   - Allez dans "🔔 NOTIFICATIONS EN TEMPS RÉEL"
   - Vous devriez voir la notification de panne

---

### **TEST 5 : Test de Signalement d'Arrêt**

1. **Connectez-vous comme opérateur**

2. **Allez dans "⏸️ SIGNALEMENT D'ARRÊTS"** :
   - Sélectionnez une machine
   - Choisissez le type d'arrêt (ex: "Pause")
   - Entrez une durée estimée (ex: 15 minutes)
   - Entrez la raison
   - Cliquez sur "⏸️ SIGNALER L'ARRÊT"
   
   **Résultat attendu** :
   - Arrêt enregistré dans les événements de cycle

---

### **TEST 6 : Test du Flux Complet**

1. **Simulez un cycle complet** :
   - Opérateur 1 (Chargement) : Valide un chargement de 100T d'Or → ROMPAD
   - Opérateur 2 (Dumper) : Reçoit la notification et accepte le transport
   - Attendez quelques secondes/minutes
   - Vérifiez le calcul du temps de cycle dans "⏱️ SUIVI DES TEMPS DE CYCLE"

2. **Répétez avec différents types de minerai** :
   - Testez avec Cuivre, Fer, Zinc
   - Vérifiez que les notifications incluent le type de minerai

---

## 🔍 VÉRIFICATIONS IMPORTANTES

### ✅ Checklist de Test

- [ ] Les notifications apparaissent en temps réel
- [ ] Les opérateurs de dumper reçoivent les notifications de chargement
- [ ] Le temps de cycle est calculé correctement
- [ ] Les pannes sont notifiées aux superviseurs
- [ ] Les arrêts sont enregistrés
- [ ] Les données sont conservées dans session_state
- [ ] L'historique des validations s'affiche correctement
- [ ] Les statistiques des cycles sont exactes

---

## 🐛 EN CAS DE PROBLÈME

1. **Les notifications n'apparaissent pas** :
   - Vérifiez que vous êtes connecté avec le bon rôle
   - Rafraîchissez la page (`st.rerun()` est appelé automatiquement)

2. **Les temps de cycle ne se calculent pas** :
   - Vérifiez que vous avez accepté un transport après un chargement
   - Vérifiez les timestamps dans les événements

3. **Les données disparaissent** :
   - Les données sont stockées dans `session_state` (temporaire)
   - Pour une persistance, il faudrait ajouter une base de données

---

## 📝 NOTES IMPORTANTES

- Les données sont stockées dans `st.session_state` (session en mémoire)
- Si vous fermez l'application, les données seront perdues
- Pour tester avec plusieurs opérateurs, utilisez plusieurs onglets/navigateurs
- Les timestamps sont en format `YYYY-MM-DD HH:MM:SS`

---

## 🎯 SCÉNARIOS DE TEST RECOMMANDÉS

### Scénario 1 : Opération Normale
1. Opérateur Chargeur → Valide chargement (Or, 50T, ROMPAD)
2. Opérateur Dumper → Accepte transport
3. Vérifier temps de cycle

### Scénario 2 : Panne Urgente
1. Opérateur → Signale panne critique
2. Superviseur → Vérifie notification
3. Mécanicien → Vérifie notification

### Scénario 3 : Arrêt Programmée
1. Opérateur → Signale arrêt (Maintenance)
2. Vérifier enregistrement dans événements

### Scénario 4 : Multiple Chargements
1. Créer plusieurs chargements
2. Tester l'acceptation séquentielle
3. Vérifier les statistiques de cycles

