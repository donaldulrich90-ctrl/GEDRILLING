# Guide d'Intégration du Système de Télémétrie IoT

## 📋 Vue d'ensemble

Le système de télémétrie a été créé dans le fichier `telemetry_system.py`. Ce guide explique comment l'intégrer dans votre application `app.py`.

## 🔧 Étapes d'intégration

### 1. Import du module

Ajoutez ces lignes au début de `app.py` (après les autres imports) :

```python
# Import du système de télémétrie IoT
try:
    from telemetry_system import (
        init_telemetry_db, load_telemetry_from_file, save_telemetry_to_file,
        fetch_telemetry_data, update_telemetry_for_machine,
        detect_fuel_theft, calculate_maintenance_time,
        create_fuel_gauge, create_hours_gauge,
        sync_offline_cache, load_offline_cache
    )
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
```

### 2. Intégration dans l'onglet CARBURANT

Dans la section `# --- CARBURANT (MULTI-DEVISE) ---`, ajoutez cette section après les KPI globaux :

```python
# 1.5. TÉLÉMÉTRIE IoT TEMPS RÉEL (NOUVEAU)
if TELEMETRY_AVAILABLE:
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("📡 TÉLÉMÉTRIE IoT - TEMPS RÉEL")
    
    # Initialiser le système de télémétrie
    init_telemetry_db()
    history, last_update = load_telemetry_from_file()
    if history:
        st.session_state.telemetry_history = history
    sync_offline_cache()
    
    # Sélection de la machine
    col_machine, col_refresh = st.columns([3, 1])
    with col_machine:
        selected_machine = st.selectbox(
            "Sélectionner une machine pour la télémétrie",
            df['ID'].tolist(),
            key="telemetry_machine_select"
        )
    with col_refresh:
        force_refresh = st.button("🔄 Actualiser", use_container_width=True, key="telemetry_refresh")
    
    # Mettre à jour les données
    if selected_machine:
        update_telemetry_for_machine(selected_machine, force_refresh=force_refresh)
        
        if selected_machine in st.session_state.telemetry_db:
            current_data = st.session_state.telemetry_db[selected_machine]
            fuel_level = current_data.get('fuel_level', 0)
            engine_hours = current_data.get('engine_hours', 0)
            
            # Afficher les jauges
            col_gauge1, col_gauge2 = st.columns(2)
            
            with col_gauge1:
                st.markdown("#### ⛽ Niveau de Carburant")
                fuel_gauge = create_fuel_gauge(fuel_level, selected_machine, "gold")
                st.plotly_chart(fuel_gauge, use_container_width=True)
            
            with col_gauge2:
                st.markdown("#### ⚙️ Heures Moteur & Maintenance")
                maintenance_info = calculate_maintenance_time(selected_machine, maintenance_interval_hours=250)
                hours_gauge = create_hours_gauge(engine_hours, maintenance_info)
                st.plotly_chart(hours_gauge, use_container_width=True)
                
                # Informations de maintenance
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%);
                            padding: 15px; border-radius: 10px; border: 2px solid #FFD700; margin-top: 10px;">
                    <p style="color: #FFD700; font-size: 14px; margin: 5px 0;">
                        <strong>Heures restantes:</strong> {maintenance_info['hours_until_maintenance']:.0f}h
                    </p>
                    <p style="color: #FFD700; font-size: 14px; margin: 5px 0;">
                        <strong>Prochaine maintenance:</strong> {maintenance_info['next_maintenance_date'].strftime('%d/%m/%Y') if maintenance_info['next_maintenance_date'] else 'N/A'}
                    </p>
                    <p style="color: #FFD700; font-size: 14px; margin: 5px 0;">
                        <strong>Utilisation:</strong> {maintenance_info['percentage_used']:.1f}%
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            # Détection de vol de carburant
            is_theft, theft_data = detect_fuel_theft(selected_machine)
            if is_theft:
                st.markdown("""
                <style>
                @keyframes blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.3; }
                }
                .theft-alert {
                    animation: blink 1s infinite;
                    background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    border: 4px solid #FFD700;
                    font-weight: 900;
                    font-size: 24px;
                    text-align: center;
                    margin: 20px 0;
                }
                </style>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="theft-alert">
                    🚨 ALERTE VOL DE CARBURANT DÉTECTÉ 🚨<br>
                    Machine: {theft_data['machine_id']}<br>
                    Baisse: {theft_data['fuel_drop']:.1f}% en {theft_data['time_window']} minutes<br>
                    De {theft_data['previous_fuel']:.1f}% à {theft_data['current_fuel']:.1f}%
                </div>
                """, unsafe_allow_html=True)
            
            # Informations GPS
            st.markdown("---")
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("📍 Latitude", f"{current_data.get('latitude', 0):.6f}")
            with col_info2:
                st.metric("📍 Longitude", f"{current_data.get('longitude', 0):.6f}")
            with col_info3:
                timestamp = current_data.get('timestamp', datetime.now().isoformat())
                st.metric("🕐 Dernière mise à jour", datetime.fromisoformat(timestamp).strftime('%H:%M:%S'))
            
            # Graphique historique
            if len(st.session_state.telemetry_history) > 0:
                st.markdown("---")
                st.markdown("#### 📊 Historique de Consommation")
                machine_history = [
                    h for h in st.session_state.telemetry_history 
                    if h.get('machine_id') == selected_machine
                ][-50:]
                
                if machine_history:
                    df_history = pd.DataFrame(machine_history)
                    df_history['timestamp'] = pd.to_datetime(df_history['timestamp'])
                    df_history = df_history.sort_values('timestamp')
                    
                    fig_consumption = go.Figure()
                    fig_consumption.add_trace(go.Scatter(
                        x=df_history['timestamp'],
                        y=df_history['fuel_level'],
                        mode='lines+markers',
                        name='Niveau Carburant (%)',
                        line=dict(color='#FFD700', width=3),
                        marker=dict(size=8, color='#FFD700')
                    ))
                    fig_consumption.update_layout(
                        title="Évolution du Niveau de Carburant",
                        xaxis_title="Temps",
                        yaxis_title="Niveau (%)",
                        plot_bgcolor='#1e1e2e',
                        paper_bgcolor='#1e1e2e',
                        font=dict(color='#FFD700'),
                        height=400
                    )
                    st.plotly_chart(fig_consumption, use_container_width=True)
        else:
            st.info(f"⏳ Chargement des données de télémétrie pour {selected_machine}...")
            update_telemetry_for_machine(selected_machine, force_refresh=True)
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
```

## 🔌 Configuration de l'API IoT

Pour utiliser une vraie API IoT, modifiez la fonction `fetch_telemetry_data()` dans `telemetry_system.py` :

1. Décommentez les lignes de l'appel API réel
2. Configurez les variables d'environnement :
   ```bash
   export IOT_API_KEY="votre_cle_api"
   export IOT_API_URL="https://votre-api-iot.com/telemetry"
   ```

## 📱 Optimisation Tablette (Samsung Galaxy Tab Active4 Pro)

Le système est déjà optimisé avec :
- Boutons de taille adaptée (minimum 60px de hauteur)
- Zones tactiles larges
- Mode hors ligne avec cache local
- Synchronisation automatique au retour en ligne

## 🎨 Style Gold & Dark

Toutes les visualisations utilisent le thème Gold & Dark :
- Jauges avec couleurs dorées (#FFD700)
- Fond sombre (#1e1e2e)
- Animations et effets visuels

## 📊 Fonctionnalités

✅ **Jauges de carburant** - Visualisation temps réel avec Plotly  
✅ **Détection de vol** - Alerte si baisse >5% en <10 minutes  
✅ **Calcul de maintenance** - Basé sur les heures moteur  
✅ **Mode hors ligne** - Cache local avec synchronisation  
✅ **Historique** - Graphiques de consommation  
✅ **GPS** - Affichage des coordonnées  

## 🚀 Utilisation

1. Le système se charge automatiquement dans l'onglet CARBURANT
2. Sélectionnez une machine dans le menu déroulant
3. Les données se mettent à jour automatiquement toutes les 30 secondes
4. Cliquez sur "🔄 Actualiser" pour forcer une mise à jour

## 📝 Notes

- Les données sont simulées par défaut (pour la démo)
- Remplacez `fetch_telemetry_data()` pour utiliser une vraie API
- Les fichiers JSON sont créés automatiquement (`telemetry_database.json`, `telemetry_offline_cache.json`)










