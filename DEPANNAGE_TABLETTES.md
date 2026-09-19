# 🔧 DÉPANNAGE - PROBLÈMES D'ACCÈS DEPUIS LES TABLETTES

## ❌ PROBLÈME 1 : Les tablettes ne peuvent pas accéder à l'application

### Solution 1 : Vérifier que Streamlit écoute sur toutes les interfaces

**Sur votre ordinateur**, arrêtez l'application (Ctrl+C) et relancez avec :

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### Solution 2 : Vérifier l'adresse IP

**Windows** :
```powershell
ipconfig
```
Cherchez "Adresse IPv4" sous votre connexion Wi-Fi/Ethernet

**Exemple** : `192.168.1.100`

### Solution 3 : Vérifier le pare-feu Windows

1. Ouvrez "Pare-feu Windows Defender"
2. Cliquez sur "Autoriser une application via le pare-feu"
3. Cherchez "Python" et cochez "Privé" et "Public"
4. Si Python n'est pas dans la liste, cliquez sur "Autoriser une autre application" et ajoutez Python

**OU** temporairement désactivez le pare-feu pour tester

### Solution 4 : Vérifier que tous les appareils sont sur le même réseau

- Ordinateur et tablettes doivent être sur le **même réseau Wi-Fi**
- Vérifiez que l'adresse IP commence par la même série (ex: tous en `192.168.1.x`)

### Solution 5 : Tester la connexion

**Sur la tablette**, dans le navigateur, essayez d'accéder à :
```
http://[ADRESSE_IP]:8501
```

Si ça ne fonctionne pas, essayez aussi :
```
http://[ADRESSE_IP]:8501/_stcore/health
```

---

## ❌ PROBLÈME 2 : L'application se charge mais les alertes ne fonctionnent pas

### Solution 1 : Vérifier que le son est activé

- Sur la tablette, vérifiez que le volume n'est pas en mode silencieux
- Testez avec un autre site web qui joue du son

### Solution 2 : Autoriser les sons dans le navigateur

- Chrome : Paramètres → Confidentialité et sécurité → Paramètres du site → Sons → Autoriser
- Safari : Paramètres → Safari → Autoriser les sons

### Solution 3 : Vérifier la console du navigateur

1. Sur la tablette, ouvrez les outils développeur (si disponible)
2. Regardez s'il y a des erreurs JavaScript
3. Cherchez des messages comme "AudioContext not available"

---

## ❌ PROBLÈME 3 : Les notifications ne s'affichent pas

### Solution 1 : Rafraîchir la page

- Sur la tablette, appuyez sur F5 ou faites un rafraîchissement
- Les notifications peuvent prendre quelques secondes à apparaître

### Solution 2 : Vérifier que les comptes sont corrects

- Vérifiez que l'opérateur de dumper sélectionné correspond bien au compte connecté sur la tablette 2
- Vérifiez dans RH que les machines sont bien assignées

---

## ❌ PROBLÈME 4 : L'application est lente ou se déconnecte

### Solution 1 : Vérifier la connexion Wi-Fi

- Assurez-vous d'avoir une bonne connexion
- Évitez les réseaux surchargés

### Solution 2 : Fermer les autres applications

- Fermez les autres applications sur les tablettes
- Fermez les autres onglets du navigateur

---

## 🆘 SOLUTION RAPIDE : Test avec localhost d'abord

Si rien ne fonctionne, testez d'abord sur l'ordinateur avec deux navigateurs :

1. **Navigateur 1** : `http://localhost:8501` → Connectez-vous avec opérateur de chargement
2. **Navigateur 2** (mode navigation privée) : `http://localhost:8501` → Connectez-vous avec opérateur de dumper

Si ça fonctionne sur l'ordinateur mais pas sur les tablettes, c'est un problème réseau.

---

## 📞 COMMANDES DE DIAGNOSTIC

### Vérifier que Streamlit écoute bien :
```bash
netstat -an | findstr 8501
```

### Tester la connexion depuis l'ordinateur :
```bash
curl http://localhost:8501/_stcore/health
```

### Vérifier l'adresse IP (Windows) :
```powershell
ipconfig /all
```

---

## 💡 SOLUTION ALTERNATIVE : Utiliser ngrok (pour test rapide)

Si le réseau local ne fonctionne pas, vous pouvez utiliser ngrok :

1. **Installez ngrok** : https://ngrok.com/download
2. **Lancez Streamlit** normalement
3. **Dans un autre terminal**, lancez :
   ```bash
   ngrok http 8501
   ```
4. **Copiez l'URL HTTPS** fournie par ngrok (ex: `https://abc123.ngrok.io`)
5. **Sur vos tablettes**, accédez à cette URL

⚠️ **Note** : ngrok est pour les tests uniquement, pas pour la production.

---

**Dites-moi quel problème spécifique vous rencontrez et je vous aiderai à le résoudre !**












