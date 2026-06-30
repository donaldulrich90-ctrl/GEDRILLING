# 🔔 GUIDE DE TEST - ALERTES SONORES

Ce guide vous explique comment tester les alertes sonores pour les opérateurs de dumper et les ingénieurs/superviseurs/mécaniciens.

## 📋 PRÉREQUIS

1. **Lancer l'application Streamlit**
   ```bash
   streamlit run app.py
   ```

2. **Avoir les comptes suivants créés** :
   - Un opérateur de chargement (avec machine Excavatrice/Chargeuse)
   - Un opérateur de dumper (avec machine Dumper/Camion)
   - Un ingénieur/superviseur/mécanicien

3. **Avoir le son activé** sur votre ordinateur/tablette

---

## 🧪 TEST 1 : ALERTE SONORE POUR OPÉRATEUR DE DUMPER

### Objectif
Tester l'alerte sonore qui se déclenche quand un opérateur de dumper reçoit un nouveau chargement.

### Étapes

1. **Ouvrir deux navigateurs** (ou un navigateur + mode navigation privée)

2. **Navigateur 1 - Opérateur de Chargement** :
   - Connectez-vous avec un compte d'opérateur de chargement
   - Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
   - Dans la section **"📦 TABLETTE DE CHARGEMENT"** :
     - Sélectionnez un opérateur de dumper
     - Choisissez un type de minerai (ex: 🥇 OR)
     - Choisissez un grade (ex: 🟢 HIGH GRADE)
     - Cliquez sur **"✅ VALIDER LE CHARGEMENT"**

3. **Navigateur 2 - Opérateur de Dumper** :
   - Connectez-vous avec le compte de l'opérateur de dumper sélectionné
   - Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
   - **🎵 L'ALERTE SONORE DOIT SE DÉCLENCHER AUTOMATIQUEMENT !**
   - Vous devriez entendre : **3 bips aigus** (bip-bip-bip)
   - Si votre appareil supporte la vibration, vous devriez aussi sentir une vibration

### Résultat attendu

✅ **Son** : 3 bips aigus (800 Hz, 800 Hz, 1000 Hz)  
✅ **Vibration** : Séquence de vibrations (si supporté)  
✅ **Visuel** : Un nouveau chargement apparaît dans la section "🚀 CHARGEMENTS EN ATTENTE DE DÉMARRAGE"

### Vérifications

- [ ] L'alerte sonore se déclenche immédiatement
- [ ] Le son est audible et clair
- [ ] La vibration fonctionne (si supporté)
- [ ] Le chargement apparaît visuellement
- [ ] L'alerte ne se répète pas si vous rafraîchissez la page (déjà alerté)

---

## 🧪 TEST 2 : ALERTE SONORE POUR INGÉNIEURS/SUPERVISEURS/MÉCANICIENS

### Objectif
Tester l'alerte sonore d'urgence qui se déclenche quand une panne est signalée.

### Étapes

1. **Ouvrir deux navigateurs** (ou un navigateur + mode navigation privée)

2. **Navigateur 1 - Opérateur** :
   - Connectez-vous avec un compte d'opérateur
   - Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
   - Dans la section **"🚨 SIGNALISATION DE PANNE"** :
     - Sélectionnez une machine
     - Choisissez un type de panne (ex: Mécanique)
     - Choisissez une gravité (ex: Critique)
     - Remplissez la description
     - Cliquez sur **"🚨 SIGNALER LA PANNE"**

3. **Navigateur 2 - Ingénieur/Superviseur/Mécanicien** :
   - Connectez-vous avec un compte d'ingénieur, superviseur ou mécanicien
   - Allez dans l'onglet **"VALIDATION OPÉRATEUR"**
   - **🚨 L'ALERTE SONORE D'URGENCE DOIT SE DÉCLENCHER AUTOMATIQUEMENT !**
   - Vous devriez entendre : **5 bips d'urgence** (séquence plus longue et plus forte)
   - Si votre appareil supporte la vibration, vous devriez sentir une vibration plus forte
   - L'écran peut clignoter légèrement en rouge

### Résultat attendu

✅ **Son** : 5 bips d'urgence (fréquences variables, type "sawtooth" - son plus agressif)  
✅ **Vibration** : Séquence de vibrations plus longue (si supporté)  
✅ **Flash visuel** : Clignotement rouge léger de l'écran (6 fois)  
✅ **Visuel** : La notification de panne apparaît

### Vérifications

- [ ] L'alerte sonore d'urgence se déclenche immédiatement
- [ ] Le son est plus fort et plus urgent que l'alerte de chargement
- [ ] La vibration est plus longue (si supporté)
- [ ] Le flash visuel rouge apparaît (optionnel)
- [ ] La notification de panne est visible
- [ ] L'alerte ne se répète pas si vous rafraîchissez la page (déjà alerté)

---

## 🔍 DÉPANNAGE

### Problème : Aucun son ne se déclenche

**Solutions** :
1. **Vérifiez le volume** de votre ordinateur/tablette
2. **Vérifiez que le navigateur n'est pas en mode silencieux**
3. **Autorisez les sons** dans les paramètres du navigateur
4. **Testez avec un autre navigateur** (Chrome, Firefox, Edge)
5. **Vérifiez la console du navigateur** (F12) pour voir s'il y a des erreurs JavaScript

### Problème : Le son se répète en boucle

**Solution** :
- C'est normal si vous rafraîchissez la page plusieurs fois
- L'alerte ne devrait sonner qu'une fois par nouveau chargement/panne
- Si le problème persiste, vérifiez que `st.session_state.alerted_loadings` et `st.session_state.alerted_breakdowns` fonctionnent correctement

### Problème : L'alerte ne se déclenche pas pour les ingénieurs

**Solutions** :
1. **Vérifiez le rôle de l'utilisateur** dans RH
2. Le rôle doit contenir un de ces mots : "Ingenieur", "Ingénieur", "Superviseur", "Mecanicien", "Mécanicien"
3. **Vérifiez que l'utilisateur est bien dans le staff** (RH > Liste Employés)

### Problème : La vibration ne fonctionne pas

**Solutions** :
1. La vibration nécessite un appareil qui la supporte (tablette, smartphone)
2. Le navigateur doit avoir l'autorisation de vibrer
3. Sur certains navigateurs, la vibration nécessite une interaction utilisateur préalable

---

## 🎯 SCÉNARIOS DE TEST COMPLETS

### Scénario 1 : Workflow complet avec alertes

1. **Chargeur** valide un chargement → **Dumper** reçoit l'alerte sonore ✅
2. **Dumper** valide le démarrage
3. **Dumper** valide le déchargement
4. **Opérateur** signale une panne → **Ingénieur** reçoit l'alerte d'urgence ✅

### Scénario 2 : Plusieurs chargements consécutifs

1. **Chargeur** valide le chargement 1 → **Dumper** reçoit l'alerte ✅
2. **Chargeur** valide le chargement 2 → **Dumper** reçoit l'alerte ✅
3. Vérifier que chaque nouveau chargement déclenche une alerte

### Scénario 3 : Pannes de différentes gravités

1. **Opérateur** signale une panne "Mineure" → **Ingénieur** reçoit l'alerte ✅
2. **Opérateur** signale une panne "Critique" → **Ingénieur** reçoit l'alerte ✅
3. Vérifier que toutes les pannes déclenchent l'alerte

---

## 📝 CHECKLIST DE TEST

### Test Alerte Dumper
- [ ] L'application est lancée
- [ ] Deux navigateurs sont ouverts
- [ ] Compte opérateur de chargement connecté
- [ ] Compte opérateur de dumper connecté
- [ ] Chargement validé par le chargeur
- [ ] Alerte sonore déclenchée chez le dumper
- [ ] Son audible (3 bips)
- [ ] Vibration fonctionne (si supporté)
- [ ] Chargement visible dans l'interface

### Test Alerte Panne
- [ ] L'application est lancée
- [ ] Deux navigateurs sont ouverts
- [ ] Compte opérateur connecté
- [ ] Compte ingénieur/superviseur/mécanicien connecté
- [ ] Panne signalée par l'opérateur
- [ ] Alerte sonore d'urgence déclenchée
- [ ] Son audible (5 bips d'urgence)
- [ ] Vibration fonctionne (si supporté)
- [ ] Flash visuel visible (optionnel)
- [ ] Notification de panne visible

---

## 💡 CONSEILS POUR UN MEILLEUR TEST

1. **Testez avec le volume à un niveau confortable** - Les alertes peuvent être fortes
2. **Utilisez des écouteurs** pour mieux entendre les différences entre les alertes
3. **Testez sur différents navigateurs** pour vérifier la compatibilité
4. **Testez sur tablette/smartphone** si possible pour la vibration
5. **Testez avec plusieurs utilisateurs simultanément** pour simuler un environnement réel

---

## 🎵 DESCRIPTION DES SONS

### Alerte Dumper (Chargement)
- **Type** : Bips aigus
- **Fréquence** : 800 Hz, 800 Hz, 1000 Hz
- **Durée** : ~1.2 secondes
- **Caractère** : Informatif, attentionné

### Alerte Panne (Urgence)
- **Type** : Bips d'urgence
- **Fréquence** : 400 Hz, 400 Hz, 300 Hz, 300 Hz, 500 Hz
- **Durée** : ~2.8 secondes
- **Caractère** : Urgent, alarmant

---

**Bon test ! 🔊**












