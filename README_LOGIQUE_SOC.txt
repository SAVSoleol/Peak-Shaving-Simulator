Logique SOC Peak Shaving Simulator

SOC technique fixe : 5 %.
Frontière Peak Shaving : réglable, 30 % par défaut.

Exemple 100 kWh / frontière 30 % :
- 0-5 % = 5 kWh non utilisables;
- 5-30 % = 25 kWh réellement disponibles pour le Peak Shaving;
- 30-100 % = 70 kWh destinés à l'autoconsommation et non utilisés par ce simulateur.

Le moteur Peak Shaving recharge désormais uniquement jusqu'à la frontière de réserve,
par le PV ou par le réseau. Il n'utilise plus la zone autoconsommation.
