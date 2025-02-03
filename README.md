# Dive-Plan

Dive-Plan est un outil de planification de plongée qui permet de calculer des profils de plongée, en tenant compte des paliers de décompression nécessaires. Il utilise des modèles de décompression pour garantir la sécurité de la plongée.

## Fonctionnalités

* **Création de profils de plongée:** Définissez des plongées avec plusieurs étapes, incluant la descente, le temps au fond et la remontée.
* **Calcul des paliers de décompression:**  Dive-Plan calcule automatiquement les paliers de décompression nécessaires en fonction du profil de plongée et du modèle de décompression choisi.
* **Gestion des mélanges gazeux:**  Prend en charge différents mélanges gazeux (air, nitrox, trimix) et permet de sélectionner le meilleur gaz pour chaque étape de la plongée.
* **Optimisation du gaz:**  Peut suggérer un mélange gazeux optimal pour une profondeur et une pression partielle d'oxygène (ppO2) cibles.
* **Gestion des bouteilles:**  Permet de spécifier les caractéristiques des bouteilles (volume, pression de service) et de suivre la consommation de gaz.
* **Gestion de la réserve:**  Prend en compte la pression de réserve et avertit si la réserve est utilisée.
* **Rapports de plongée:**  Génère des rapports de plongée lisibles par l'utilisateur, affichant les étapes de la plongée, les profondeurs, les temps et les paliers.

## Utilisation

**Installation:**

Ce projet est en Python. Assurez-vous d'avoir Python installé. Vous pouvez ensuite installer les dépendances nécessaires.  (Détails d'installation à ajouter si des dépendances spécifiques sont requises).

**Exemple d'utilisation:**

```python
from diveplan.core import dive, gas

# Définir les mélanges gazeux
air = gas.GasMixture(o2_fraction=constants.AIR_FO2, n2_fraction=constants.AIR_FN2)
nx50 = gas.GasMixture(o2_fraction=0.5)

# Définir les bouteilles
cylinder_air = gas.GasCylinder(volume=12, working_pressure=200, gas_mixture=air, reserve_pressure=50)
cylinder_nx50 = gas.GasCylinder(volume=10, working_pressure=200, gas_mixture=nx50, reserve_pressure=50)


# Définir les étapes de la plongée
steps = [
    dive.DiveStep(time=5, start_depth=0, end_depth=20, gas_cylinder=cylinder_air),
    dive.DiveStep(time=20, start_depth=20, end_depth=20, gas_cylinder=cylinder_air),
    dive.DiveStep(time=5, start_depth=20, end_depth=5, gas_cylinder=cylinder_nx50), # Remontée à 5m avec Nitrox 50
]

# Créer l'objet Dive
my_dive = dive.Dive(planned_steps=steps, gas_cylinders=[cylinder_air, cylinder_nx50], gradient_factors=(85,85))

# Calculer les étapes de la plongée et les paliers
my_dive.calculate_steps()
my_dive.calculate_ascent()

# Afficher le rapport de plongée
my_dive.report()


# Exemple d'ajout d'une bouteille optimale
my_dive.add_optimal_gas_cylinder(volume=7, working_pressure=232, end_depth=20, target_ppo2=1.4)
