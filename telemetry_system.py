"""
Système de Télémétrie IoT pour GOOD ENGINEERS OS
Gère la récupération, le stockage et l'affichage des données de télémétrie
des machines (carburant, heures moteur, GPS)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import time
import random
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Clé API pour l'IoT (à remplacer par la vraie clé plus tard)
IOT_API_KEY = os.getenv("IOT_API_KEY", "demo_key_12345")
IOT_API_URL = os.getenv("IOT_API_URL", "https://api.iot-demo.com/telemetry")

# Fichiers de stockage
TELEMETRY_DB_FILE = "telemetry_database.json"
OFFLINE_CACHE_FILE = "telemetry_offline_cache.json"

# Seuil d'alerte vol de carburant (5% en 10 minutes)
FUEL_THEFT_THRESHOLD = 5.0  # Pourcentage
FUEL_THEFT_TIME_WINDOW = 10  # Minutes

# ==============================================================================
# STRUCTURE DE BASE DE DONNÉES
# ==============================================================================

def init_telemetry_db():
    """Initialise la base de données de télémétrie dans session_state"""
    if 'telemetry_db' not in st.session_state:
        st.session_state.telemetry_db = {}
    
    if 'telemetry_history' not in st.session_state:
        st.session_state.telemetry_history = []

def load_telemetry_from_file():
    """Charge l'historique de télémétrie depuis le fichier JSON"""
    if os.path.exists(TELEMETRY_DB_FILE):
        try:
            with open(TELEMETRY_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('history', []), data.get('last_update', {})
        except:
            return [], {}
    return [], {}

def save_telemetry_to_file():
    """Sauvegarde l'historique de télémétrie dans le fichier JSON"""
    try:
        data = {
            'history': st.session_state.telemetry_history[-1000:],  # Garder les 1000 dernières entrées
            'last_update': {machine_id: datetime.now().isoformat() 
                          for machine_id in st.session_state.telemetry_db.keys()},
            'last_sync': datetime.now().isoformat()
        }
        with open(TELEMETRY_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde: {e}")

# ==============================================================================
# RÉCUPÉRATION DES DONNÉES IoT (SIMULÉE)
# ==============================================================================

def fetch_telemetry_data(machine_id: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Récupère les données de télémétrie depuis le serveur IoT
    
    Args:
        machine_id: ID de la machine
        use_cache: Utiliser le cache si la requête échoue
    
    Returns:
        Dict avec fuel_level, engine_hours, latitude, longitude, timestamp
        ou None si erreur
    """
    # SIMULATION - À remplacer par un vrai appel API
    try:
        # Simuler un appel API
        import requests
        
        headers = {
            "Authorization": f"Bearer {IOT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "machine_id": machine_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Pour la démo, on simule une réponse
        # Décommenter pour utiliser la vraie API :
        # response = requests.get(f"{IOT_API_URL}/{machine_id}", headers=headers, params=params, timeout=5)
        # if response.status_code == 200:
        #     return response.json()
        
        # SIMULATION DES DONNÉES
        current_time = datetime.now()
        
        # Générer des données réalistes avec variation
        base_fuel = 75.0 + random.uniform(-5, 5)  # Entre 70% et 80%
        base_hours = 1250.0 + random.uniform(-10, 10)
        
        telemetry_data = {
            "machine_id": machine_id,
            "fuel_level": max(0, min(100, base_fuel)),  # Entre 0 et 100%
            "engine_hours": max(0, base_hours),
            "latitude": 6.4969 + random.uniform(-0.01, 0.01),  # Coordonnées exemple (Burkina Faso)
            "longitude": -1.3072 + random.uniform(-0.01, 0.01),
            "timestamp": current_time.isoformat(),
            "speed": random.uniform(0, 50),  # km/h
            "rpm": random.uniform(800, 2200),  # Tours/minute
            "temperature": random.uniform(85, 95),  # °C
            "battery_voltage": random.uniform(12.0, 14.5)  # Volts
        }
        
        return telemetry_data
        
    except Exception as e:
        st.warning(f"Erreur de connexion IoT pour {machine_id}: {e}")
        
        # Utiliser le cache si disponible
        if use_cache and machine_id in st.session_state.telemetry_db:
            cached_data = st.session_state.telemetry_db[machine_id]
            cached_data['timestamp'] = datetime.now().isoformat()
            return cached_data
        
        return None

# ==============================================================================
# GESTION DU MODE HORS LIGNE
# ==============================================================================

def load_offline_cache():
    """Charge le cache hors ligne"""
    if os.path.exists(OFFLINE_CACHE_FILE):
        try:
            with open(OFFLINE_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_to_offline_cache(telemetry_data: Dict):
    """Sauvegarde les données dans le cache hors ligne"""
    cache = load_offline_cache()
    cache.append({
        **telemetry_data,
        'cached_at': datetime.now().isoformat()
    })
    try:
        with open(OFFLINE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erreur cache hors ligne: {e}")

def sync_offline_cache():
    """Synchronise le cache hors ligne avec le serveur"""
    cache = load_offline_cache()
    if not cache:
        return
    
    synced = []
    for item in cache:
        try:
            # Ici, on enverrait les données au serveur
            # Pour la démo, on les ajoute juste à l'historique
            st.session_state.telemetry_history.append(item)
            synced.append(item)
        except:
            pass
    
    # Supprimer les éléments synchronisés
    remaining = [item for item in cache if item not in synced]
    if remaining:
        with open(OFFLINE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)
    else:
        os.remove(OFFLINE_CACHE_FILE)

# ==============================================================================
# DÉTECTION DE VOL DE CARBURANT
# ==============================================================================

def detect_fuel_theft(machine_id: str) -> Tuple[bool, Optional[Dict]]:
    """
    Détecte un vol de carburant (baisse de >5% en <10 minutes)
    
    Returns:
        (is_theft_detected, alert_data)
    """
    if machine_id not in st.session_state.telemetry_db:
        return False, None
    
    current_data = st.session_state.telemetry_db[machine_id]
    current_fuel = current_data.get('fuel_level', 0)
    current_time = datetime.fromisoformat(current_data.get('timestamp', datetime.now().isoformat()))
    
    # Chercher dans l'historique les données des 10 dernières minutes
    time_threshold = current_time - timedelta(minutes=FUEL_THEFT_TIME_WINDOW)
    
    recent_history = [
        h for h in st.session_state.telemetry_history
        if h.get('machine_id') == machine_id
        and datetime.fromisoformat(h.get('timestamp', '')) >= time_threshold
    ]
    
    if not recent_history:
        return False, None
    
    # Trouver le niveau de carburant le plus élevé dans la fenêtre
    max_fuel = max([h.get('fuel_level', 0) for h in recent_history])
    
    fuel_drop = max_fuel - current_fuel
    
    if fuel_drop > FUEL_THEFT_THRESHOLD:
        return True, {
            'machine_id': machine_id,
            'fuel_drop': fuel_drop,
            'previous_fuel': max_fuel,
            'current_fuel': current_fuel,
            'time_window': FUEL_THEFT_TIME_WINDOW,
            'detected_at': current_time.isoformat()
        }
    
    return False, None

# ==============================================================================
# CALCUL DE MAINTENANCE
# ==============================================================================

def calculate_maintenance_time(machine_id: str, maintenance_interval_hours: int = 250) -> Dict:
    """
    Calcule le temps restant avant la prochaine maintenance
    
    Args:
        machine_id: ID de la machine
        maintenance_interval_hours: Intervalle de maintenance en heures (défaut: 250h)
    
    Returns:
        Dict avec hours_until_maintenance, next_maintenance_date, etc.
    """
    if machine_id not in st.session_state.telemetry_db:
        return {
            'hours_until_maintenance': maintenance_interval_hours,
            'next_maintenance_date': None,
            'current_hours': 0,
            'maintenance_interval': maintenance_interval_hours,
            'percentage_used': 0
        }
    
    current_data = st.session_state.telemetry_db[machine_id]
    current_hours = current_data.get('engine_hours', 0)
    
    # Trouver la dernière maintenance dans l'historique
    last_maintenance_hours = 0
    for entry in reversed(st.session_state.telemetry_history):
        if entry.get('machine_id') == machine_id and entry.get('maintenance_done'):
            last_maintenance_hours = entry.get('engine_hours', 0)
            break
    
    hours_since_maintenance = current_hours - last_maintenance_hours
    hours_until_maintenance = max(0, maintenance_interval_hours - hours_since_maintenance)
    
    # Estimer la date de la prochaine maintenance (basé sur l'utilisation moyenne)
    # Pour simplifier, on suppose 8h/jour d'utilisation
    avg_hours_per_day = 8
    days_until_maintenance = hours_until_maintenance / avg_hours_per_day if avg_hours_per_day > 0 else 0
    next_maintenance_date = datetime.now() + timedelta(days=days_until_maintenance)
    
    percentage_used = (hours_since_maintenance / maintenance_interval_hours * 100) if maintenance_interval_hours > 0 else 0
    
    return {
        'hours_until_maintenance': hours_until_maintenance,
        'next_maintenance_date': next_maintenance_date,
        'current_hours': current_hours,
        'hours_since_maintenance': hours_since_maintenance,
        'maintenance_interval': maintenance_interval_hours,
        'percentage_used': min(100, percentage_used),
        'last_maintenance_hours': last_maintenance_hours
    }

# ==============================================================================
# VISUALISATION - JAUGE DE CARBURANT
# ==============================================================================

def create_fuel_gauge(fuel_level: float, machine_id: str, color_scheme: str = "gold") -> go.Figure:
    """
    Crée une jauge dorée pour le niveau de carburant
    
    Args:
        fuel_level: Niveau de carburant (0-100)
        machine_id: ID de la machine
        color_scheme: "gold" ou "dark"
    """
    # Définir les couleurs selon le schéma
    if color_scheme == "gold":
        colors = {
            'low': '#f44336',      # Rouge
            'medium': '#FF9800',   # Orange
            'high': '#4CAF50',     # Vert
            'gauge': '#FFD700',    # Or
            'bg': '#1e1e2e'        # Fond sombre
        }
    else:
        colors = {
            'low': '#f44336',
            'medium': '#FF9800',
            'high': '#4CAF50',
            'gauge': '#667eea',
            'bg': '#1e1e2e'
        }
    
    # Déterminer la couleur selon le niveau
    if fuel_level < 20:
        gauge_color = colors['low']
    elif fuel_level < 50:
        gauge_color = colors['medium']
    else:
        gauge_color = colors['high']
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = fuel_level,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"<b>{machine_id}</b><br>Carburant", 'font': {'size': 24, 'color': '#FFD700'}},
        delta = {'reference': 100, 'position': "top", 'font': {'size': 20, 'color': '#FFD700'}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 2, 'tickcolor': "#FFD700"},
            'bar': {'color': gauge_color, 'thickness': 0.3},
            'bgcolor': colors['bg'],
            'borderwidth': 3,
            'bordercolor': colors['gauge'],
            'steps': [
                {'range': [0, 20], 'color': colors['low']},
                {'range': [20, 50], 'color': colors['medium']},
                {'range': [50, 100], 'color': colors['high']}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 10
            }
        },
        number = {'font': {'size': 40, 'color': '#FFD700', 'family': 'Arial Black'}}
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#FFD700", 'family': "Arial"},
        height=300,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

# ==============================================================================
# VISUALISATION - JAUGE D'HEURES MOTEUR
# ==============================================================================

def create_hours_gauge(current_hours: float, maintenance_info: Dict) -> go.Figure:
    """Crée une jauge pour les heures moteur et la maintenance"""
    max_hours = maintenance_info['maintenance_interval']
    hours_used = maintenance_info['hours_since_maintenance']
    percentage = maintenance_info['percentage_used']
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = hours_used,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"<b>Heures Moteur</b><br>Avant Maintenance", 'font': {'size': 24, 'color': '#FFD700'}},
        gauge = {
            'axis': {'range': [None, max_hours], 'tickwidth': 2, 'tickcolor': "#FFD700"},
            'bar': {'color': '#FFD700', 'thickness': 0.3},
            'bgcolor': '#1e1e2e',
            'borderwidth': 3,
            'bordercolor': '#FFD700',
            'steps': [
                {'range': [0, max_hours * 0.5], 'color': '#4CAF50'},
                {'range': [max_hours * 0.5, max_hours * 0.8], 'color': '#FF9800'},
                {'range': [max_hours * 0.8, max_hours], 'color': '#f44336'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_hours * 0.9
            }
        },
        number = {
            'font': {'size': 40, 'color': '#FFD700', 'family': 'Arial Black'},
            'suffix': f" / {max_hours}h"
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#FFD700", 'family': "Arial"},
        height=300,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

# ==============================================================================
# FONCTION PRINCIPALE DE MISE À JOUR
# ==============================================================================

def update_telemetry_for_machine(machine_id: str, force_refresh: bool = False):
    """
    Met à jour les données de télémétrie pour une machine
    
    Args:
        machine_id: ID de la machine
        force_refresh: Forcer le rafraîchissement même si récent
    """
    init_telemetry_db()
    
    # Vérifier si on doit rafraîchir (toutes les 30 secondes par défaut)
    last_update_key = f"telemetry_last_update_{machine_id}"
    if not force_refresh and last_update_key in st.session_state:
        last_update = st.session_state[last_update_key]
        if (datetime.now() - last_update).seconds < 30:
            return  # Trop récent, ne pas rafraîchir
    
    # Récupérer les données
    telemetry_data = fetch_telemetry_data(machine_id)
    
    if telemetry_data:
        # Mettre à jour la base de données
        st.session_state.telemetry_db[machine_id] = telemetry_data
        st.session_state.telemetry_history.append(telemetry_data)
        st.session_state[last_update_key] = datetime.now()
        
        # Sauvegarder dans le fichier
        save_telemetry_to_file()
    else:
        # Mode hors ligne - sauvegarder dans le cache
        if machine_id in st.session_state.telemetry_db:
            cached_data = st.session_state.telemetry_db[machine_id].copy()
            cached_data['timestamp'] = datetime.now().isoformat()
            cached_data['offline'] = True
            save_to_offline_cache(cached_data)


