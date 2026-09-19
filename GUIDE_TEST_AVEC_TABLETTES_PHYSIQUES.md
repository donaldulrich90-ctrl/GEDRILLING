# 📱 GUIDE DE TEST AVEC DEUX TABLETTES PHYSIQUES

Ce guide vous explique comment tester le système de tablettes de chargement et déchargement avec deux tablettes réelles.

## 📋 PRÉREQUIS

1. **Deux tablettes** (Android, iPad, ou Windows)
2. **Ordinateur avec l'application Streamlit lancée**
3. **Tous les appareils connectés au même réseau Wi-Fi**

---

## 🚀 ÉTAPE 1 : LANCER L'APPLICATION SUR L'ORDINATEUR

### Sur votre ordinateur :

1. **Ouvrez un terminal** dans le dossier du projet
2. **Lancez l'application** :
   ```bash
   streamlit run app.py
   ```

3. **Notez l'adresse IP de votre ordinateur** :
   - **Windows** : Ouvrez PowerShell et tapez `ipconfig`
     - Cherchez "Adresse IPv4" (ex: `192.168.1.100`)
   - **Mac/Linux** : Ouvrez Terminal et tapez `ifconfig` ou `ip addr`
     - Cherchez votre adresse IP locale (ex: `192.168.1.100`)

4. **L'application devrait afficher** :
   ```
   You can now view your Streamlit app in your browser.
   Local URL: http://localhost:8501
   Network URL: http://192.168.1.100:8501
   ```
   - Notez l'adresse **Network URL** (ex: `http://192.168.1.100:8501`)

---

## 📱 ÉTAPE 2 : CONFIGURER LA TABLETTE 1 (OPÉRATEUR DE CHARGEMENT)

### Sur la Tablette 1 :

1. **Ouvrez le navigateur** (Chrome, Safari, Firefox, Edge)
2. **Dans la barre d'adresse**, tapez :
   ```
   http://[ADRESSE_IP_ORDINATEUR]:8501
   ```
   Exemple : `http://192.168.1.100:8501`

3. **Connectez-vous** avec un compte d'opérateur de chargement
   - Si vous n'avez pas encore de compte, créez-le d'abord sur l'ordinateur en tant qu'ADMIN

4. **Allez dans l'onglet "VALIDATION OPÉRATEUR"**
   - Vous devriez voir l'interface **"📦 TABLETTE DE CHARGEMENT"**

5. **Configurez le navigateur pour tablette** :
   - Activez le mode plein écran si disponible
   - Assurez-vous que le son est activé
   - Autorisez les notifications si demandé

---

## 📱 ÉTAPE 3 : CONFIGURER LA TABLETTE 2 (OPÉRATEUR DE DUMPER)

### Sur la Tablette 2 :

1. **Ouvrez le navigateur** (Chrome, Safari, Firefox, Edge)
2. **Dans la barre d'adresse**, tapez :
   ```
   http://[ADRESSE_IP_ORDINATEUR]:8501
   ```
   Exemple : `http://192.168.1.100:8501`

3. **Connectez-vous** avec un compte d'opérateur de dumper
   - Si vous n'avez pas encore de compte, créez-le d'abord sur l'ordinateur en tant qu'ADMIN

4. **Allez dans l'onglet "VALIDATION OPÉRATEUR"**
   - Vous devriez voir l'interface **"🚚 TABLETTE DE DÉCHARGEMENT"**

5. **Configurez le navigateur pour tablette** :
   - Activez le mode plein écran si disponible
   - Assurez-vous que le son est activé (important pour les alertes)
   - Autorisez les notifications si demandé

---

## 🧪 ÉTAPE 4 : TESTER LE WORKFLOW COMPLET

### Scénario de test :

#### Sur la Tablette 1 (Chargement) :

1. **Sélectionnez l'opérateur de dumper** dans la liste
   - Vous devriez voir le camion assigné automatiquement

2. **Choisissez le type de minerai** :
   - Cliquez sur un bouton (ex: 🥇 OR)

3. **Choisissez le grade** :
   - Cliquez sur un bouton (ex: 🟢 HIGH GRADE)

4. **Validez le chargement** :
   - Cliquez sur **"✅ VALIDER LE CHARGEMENT"**
   - Un message de succès devrait apparaître

#### Sur la Tablette 2 (Déchargement) :

1. **L'alerte sonore devrait se déclencher automatiquement** 🔔
   - Vous devriez entendre 3 bips aigus
   - La tablette devrait vibrer (si supporté)

2. **Un nouveau chargement apparaît** dans la section "🚀 CHARGEMENTS EN ATTENTE DE DÉMARRAGE"

3. **Validez le démarrage** :
   - Cliquez sur **"✅ VALIDER DÉMARRAGE"**
   - Le chargement passe en "📦 CHARGEMENTS EN COURS DE TRANSPORT"

4. **Validez le déchargement** :
   - Cliquez sur **"✅ VALIDER DÉCHARGEMENT"**
   - Les métriques s'affichent (temps de cycle, consommation carburant)
   - La directive pour la prochaine pelle s'affiche

---

## 🔧 CONFIGURATION OPTIMALE POUR TABLETTES

### Paramètres recommandés :

1. **Mode plein écran** :
   - Sur Android : Menu → Mode plein écran
   - Sur iPad : Double-tap sur la barre d'adresse pour masquer les barres

2. **Orientation** :
   - Mode paysage (horizontal) recommandé pour une meilleure visibilité

3. **Son et vibrations** :
   - Assurez-vous que le volume est activé
   - Activez les vibrations dans les paramètres de la tablette

4. **Rafraîchissement automatique** (optionnel) :
   - Certains navigateurs permettent un rafraîchissement automatique
   - Ou utilisez une extension de rafraîchissement automatique

---

## 🌐 DÉPANNAGE RÉSEAU

### Problème : Les tablettes ne peuvent pas accéder à l'application

**Solutions** :

1. **Vérifiez que tous les appareils sont sur le même réseau Wi-Fi**
   - Ordinateur et tablettes doivent être sur le même réseau

2. **Vérifiez le pare-feu Windows** :
   - Ouvrez "Pare-feu Windows Defender"
   - Autorisez Python ou Streamlit à traverser le pare-feu
   - Ou désactivez temporairement le pare-feu pour tester

3. **Vérifiez l'adresse IP** :
   - Assurez-vous d'utiliser l'adresse IP correcte de l'ordinateur
   - L'adresse doit être celle du réseau local (commence généralement par 192.168.x.x ou 10.0.x.x)

4. **Testez la connexion** :
   - Sur la tablette, essayez d'accéder à `http://[ADRESSE_IP]:8501`
   - Si ça ne fonctionne pas, vérifiez que Streamlit écoute sur toutes les interfaces :
     ```bash
     streamlit run app.py --server.address 0.0.0.0
     ```

### Problème : L'application est lente sur les tablettes

**Solutions** :

1. **Vérifiez la connexion Wi-Fi** :
   - Assurez-vous d'avoir une bonne connexion
   - Évitez les réseaux surchargés

2. **Fermez les autres applications** sur les tablettes

3. **Utilisez un navigateur récent** :
   - Chrome, Firefox, Safari (dernière version)

---

## 📱 NAVIGATEURS RECOMMANDÉS PAR PLATEFORME

### Android :
- ✅ **Chrome** (recommandé)
- ✅ Firefox
- ✅ Edge

### iPad :
- ✅ **Safari** (recommandé)
- ✅ Chrome
- ✅ Firefox

### Windows Tablets :
- ✅ **Edge** (recommandé)
- ✅ Chrome
- ✅ Firefox

---

## 🎯 TEST COMPLET AVEC DEUX TABLETTES

### Checklist :

- [ ] Ordinateur : Application Streamlit lancée
- [ ] Ordinateur : Adresse IP notée
- [ ] Tablette 1 : Accès à l'application réussi
- [ ] Tablette 1 : Connectée avec opérateur de chargement
- [ ] Tablette 1 : Interface de chargement visible
- [ ] Tablette 2 : Accès à l'application réussi
- [ ] Tablette 2 : Connectée avec opérateur de dumper
- [ ] Tablette 2 : Interface de déchargement visible
- [ ] Tablette 1 : Chargement validé
- [ ] Tablette 2 : Alerte sonore déclenchée ✅
- [ ] Tablette 2 : Démarrage validé
- [ ] Tablette 2 : Déchargement validé
- [ ] Tablette 2 : Métriques affichées
- [ ] Tablette 2 : Directive prochaine pelle affichée

---

## 💡 CONSEILS POUR UN MEILLEUR TEST

1. **Placez les tablettes côte à côte** pour voir les deux interfaces simultanément

2. **Testez les alertes sonores** :
   - Assurez-vous que le volume est activé sur la tablette 2
   - Testez avec différents volumes pour trouver le niveau optimal

3. **Testez la vibration** :
   - Si vos tablettes supportent la vibration, elle devrait se déclencher avec les alertes

4. **Testez plusieurs cycles** :
   - Validez plusieurs chargements consécutifs
   - Vérifiez que chaque nouveau chargement déclenche une alerte

5. **Testez les pannes** :
   - Sur la tablette 1, signalez une panne
   - Si vous avez une troisième tablette avec un compte ingénieur/superviseur, testez l'alerte de panne

---

## 🔒 SÉCURITÉ

⚠️ **Important** : L'application est accessible sur votre réseau local. Pour un déploiement en production :

1. Utilisez un serveur dédié
2. Configurez HTTPS
3. Ajoutez une authentification renforcée
4. Limitez l'accès au réseau

---

## 📞 COMMANDES UTILES

### Lancer Streamlit en mode réseau :
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### Trouver l'adresse IP (Windows) :
```powershell
ipconfig | findstr IPv4
```

### Trouver l'adresse IP (Mac/Linux) :
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

---

**Bon test avec vos tablettes ! 📱📱**












