#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérifie que le dossier projet contient tout ce qu’il faut pour un build Docker
identique au poste local (avant copie WinSCP / build sur le VPS).

Usage (dans ce dossier) :
  python verify_deploy_bundle.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Fichiers copiés par le Dockerfile actuel
REQUIRED_FILES = [
    ROOT / "Dockerfile",
    ROOT / "docker-compose.yml",
    ROOT / "requirements.txt",
    ROOT / "app.py",
    ROOT / "equipment_models_catalog.py",
    ROOT / ".streamlit" / "config.toml",
]

REQUIRED_DIRS = [
    ROOT / "assets",
]

# Images optionnelles mais recommandées pour la même UI qu’en local (app.py)
RECOMMENDED_PNG = [
    ROOT / "assets" / "good_engineers_hero_masthead.png",
    ROOT / "assets" / "good_engineers_logo.png",
    ROOT / "assets" / "good_engineers_brand_card.png",
]

APP_MARKER = "_ensure_fleet_summary_df"


def main() -> int:
    os.chdir(ROOT)
    errors: list[str] = []
    warnings: list[str] = []

    print("=== Vérification bundle déploiement (GOOD ENGINEERS) ===\n")
    print(f"Dossier : {ROOT}\n")

    for p in REQUIRED_FILES:
        if p.is_file():
            size = p.stat().st_size
            print(f"  [OK] fichier  {p.relative_to(ROOT)}  ({size:,} o)")
        else:
            errors.append(f"MANQUANT (obligatoire) : {p.relative_to(ROOT)}")

    for d in REQUIRED_DIRS:
        if d.is_dir():
            n = sum(1 for _ in d.rglob("*") if _.is_file())
            print(f"  [OK] dossier  {d.relative_to(ROOT)}/  ({n} fichier(s))")
        else:
            errors.append(f"MANQUANT (obligatoire) : {d.relative_to(ROOT)}/")

    app_path = ROOT / "app.py"
    if app_path.is_file():
        text = app_path.read_text(encoding="utf-8", errors="replace")
        if APP_MARKER not in text:
            errors.append(f"app.py ne contient pas le marqueur {APP_MARKER!r} (fichier trop ancien ?)")
        else:
            print(f"  [OK] app.py contient le marqueur {APP_MARKER!r}")

    print("\n--- Images bandeau (recommandé pour parité locale / VPS) ---")
    any_png = False
    for p in RECOMMENDED_PNG:
        if p.is_file():
            any_png = True
            print(f"  [OK] {p.relative_to(ROOT)}")
        else:
            warnings.append(f"absent : {p.relative_to(ROOT)} (hero ou logos dégradés en ligne)")

    if not any_png:
        warnings.append(
            "Aucun PNG recommande dans assets/ - UI en ligne peut differer (fallback)."
        )

    print("\n--- Rappel .dockerignore (non inclus dans l'image Docker) ---")
    print("  tenant_data/, logos/, images_engins/, geo_data.db, app_database.json, *.md = donnees dev locales.")
    print("  En prod, les données vivent dans le volume Docker (/data), pas forcément dans ce dossier.\n")

    if warnings:
        print("Avertissements :")
        for w in warnings:
            print(f"  ! {w}")
        print()

    if errors:
        print("ERREURS :")
        for e in errors:
            print(f"  X {e}")
        print("\nCorrigez puis relancez ce script avant WinSCP / docker build.")
        return 1

    print("Resume : pret pour docker compose build sur le serveur (fichiers Docker).")
    if warnings:
        print("Revoir les avertissements ci-dessus pour l’apparence (PNG).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
